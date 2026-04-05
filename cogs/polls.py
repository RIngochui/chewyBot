"""
Polls & Scheduling cog for chewyBot.

Provides rich interactive polls with scheduling, recurring weekly automation,
vote-limit enforcement via reaction removal, and clean embed formatting
consistent with the rest of chewyBot.

Slash commands (all under /poll group):
  /poll create            — immediate poll with duration
  /poll schedule          — poll posted at a future time
  /poll schedule_weekly   — recurring weekly poll
  /poll results           — live vote counts
  /poll close             — close and post results
  /poll list              — list all active / scheduled polls
  /poll cancel            — cancel a poll or recurring series
  /poll edit_recurring    — update a recurring poll's schedule

All SQL goes through database/queries.py — zero inline SQL here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import config, EMBED_COLOR
from database.db import get_db
from database.queries import (
    INSERT_POLL,
    UPDATE_POLL_MESSAGE_ID,
    SELECT_POLL_BY_ID,
    SELECT_POLL_BY_MESSAGE_ID,
    SELECT_ACTIVE_POLLS,
    SELECT_ALL_POLLS_FOR_LIST,
    CLOSE_POLL,
    SELECT_VOTE_COUNT_BY_USER,
    SELECT_VOTES_BY_USER,
    INSERT_POLL_VOTE,
    DELETE_POLL_VOTE,
    SELECT_VOTES_BY_POLL,
    SELECT_DISTINCT_VOTERS,
    INSERT_RECURRING_POLL,
    SELECT_ACTIVE_RECURRING_POLLS,
    SELECT_RECURRING_POLL_BY_ID,
    DEACTIVATE_RECURRING_POLL,
    UPDATE_RECURRING_POLL,
)

logger = logging.getLogger(__name__)

# Option emojis for polls (supports up to 9 options)
_OPTION_EMOJIS: list[str] = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]

# Map emoji string → 0-based option index
_EMOJI_TO_IDX: dict[str, int] = {e: i for i, e in enumerate(_OPTION_EMOJIS)}
# Also map bare keycap names Discord may send (U+20E3 only variant)
for _i, _base in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9"]):
    _EMOJI_TO_IDX[f"{_base}\u20e3"] = _i

# Weekday name → weekday() integer (Monday=0)
_WEEKDAY_MAP: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def _parse_duration(s: str) -> Optional[timedelta]:
    """Parse "Xm", "Xh", "Xd" (case-insensitive). Return None if invalid."""
    match = re.fullmatch(r"(\d+)\s*([mhd])", s.strip().lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    return None


def _parse_datetime(s: str) -> Optional[datetime]:
    """Parse a datetime string into a timezone-aware UTC datetime.

    Attempts:
    1. dateparser (if available) with PREFER_DATES_FROM=future
    2. ISO "YYYY-MM-DD HH:MM" — interpreted as UTC
    3. "Weekday H:MMam/pm" — next occurrence of that weekday at that time (UTC)
    """
    s = s.strip()

    # --- Attempt 1: dateparser ---
    try:
        import dateparser  # type: ignore[import]
        result = dateparser.parse(
            s,
            settings={"RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"},
        )
        if result is not None:
            return result.astimezone(timezone.utc)
    except ImportError:
        pass

    # --- Attempt 2: ISO "YYYY-MM-DD HH:MM" ---
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    # --- Attempt 3: "Weekday H:MMam" or "Weekday H:MMpm" ---
    match = re.fullmatch(
        r"(\w+)\s+(\d{1,2}):(\d{2})\s*(am|pm)", s, re.IGNORECASE
    )
    if match:
        day_str = match.group(1).lower()
        hour = int(match.group(2))
        minute = int(match.group(3))
        ampm = match.group(4).lower()
        if day_str in _WEEKDAY_MAP:
            if ampm == "pm" and hour != 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
            try:
                return _next_weekday_at(day_str.capitalize(), f"{hour:02d}:{minute:02d}")
            except ValueError:
                pass

    return None


def _next_weekday_at(day_name: str, time_str: str) -> datetime:
    """Compute the next UTC datetime for the given weekday name at time_str (HH:MM, 24h).

    If today is that weekday but the time has already passed, return next week.
    Always returns a timezone-aware UTC datetime.
    """
    target_weekday = _WEEKDAY_MAP[day_name.lower()]
    hour, minute = map(int, time_str.split(":"))
    now = datetime.now(timezone.utc)
    days_ahead = (target_weekday - now.weekday()) % 7
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
        days=days_ahead
    )
    if candidate <= now:
        candidate += timedelta(weeks=1)
    return candidate


def _has_manage_guild(interaction: discord.Interaction) -> bool:
    """Return True if the interacting member has Manage Guild permission."""
    if not isinstance(interaction.user, discord.Member):
        return False
    return interaction.user.guild_permissions.manage_guild


def _build_bar(pct: float) -> str:
    """Build a 10-char percentage bar using block characters."""
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


def _build_poll_embed(
    poll_id: int,
    question: str,
    options: list[str],
    close_at: datetime,
    *,
    max_choices: Optional[int] = None,
    recurring_day: Optional[str] = None,
    post_time: Optional[str] = None,
) -> discord.Embed:
    """Build the initial poll embed posted to the channel."""
    embed = discord.Embed(title=f"📊 {question}", color=EMBED_COLOR)

    description_lines: list[str] = []
    if recurring_day and post_time:
        description_lines.append(f"🔁 Weekly Poll — every {recurring_day} at {post_time}")
    if max_choices is not None:
        if max_choices == 1:
            description_lines.append("Single choice poll — pick one")
        else:
            description_lines.append(f"You can select up to {max_choices} option(s)")
    if description_lines:
        embed.description = "\n".join(description_lines)

    for i, option in enumerate(options):
        embed.add_field(
            name=f"{_OPTION_EMOJIS[i]} {option}",
            value="0 votes",
            inline=False,
        )

    close_str = close_at.strftime("%Y-%m-%d %H:%M UTC")
    embed.set_footer(text=f"Poll closes at {close_str} | Poll ID: {poll_id}")
    return embed


def _build_results_embed(
    poll_id: int,
    question: str,
    options: list[str],
    vote_counts: dict[int, int],
    distinct_voters: int,
    *,
    still_open: bool = False,
    recurring_day: Optional[str] = None,
    post_time: Optional[str] = None,
) -> discord.Embed:
    """Build the results summary embed."""
    embed = discord.Embed(title=f"📊 Poll Closed — {question}", color=EMBED_COLOR)

    description_lines: list[str] = []
    if recurring_day and post_time:
        description_lines.append(
            f"🔁 Next poll posts {recurring_day} at {post_time}"
        )
    if description_lines:
        embed.description = "\n".join(description_lines)

    total_votes = sum(vote_counts.values())
    max_count = max(vote_counts.values(), default=0)

    for i, option in enumerate(options):
        count = vote_counts.get(i, 0)
        pct = (count / total_votes * 100) if total_votes > 0 else 0.0
        bar = _build_bar(pct)
        label = f"**{option}**" if count == max_count and max_count > 0 else option
        embed.add_field(
            name=f"{_OPTION_EMOJIS[i]} {label}",
            value=f"{bar} {pct:.0f}% ({count} votes)",
            inline=False,
        )

    footer_parts = [f"Poll ID: {poll_id}", f"Total votes: {total_votes}", f"Total voters: {distinct_voters}"]
    if still_open:
        footer_parts.append("(poll still open)")
    embed.set_footer(text=" | ".join(footer_parts))
    return embed


class PollsCog(commands.Cog, name="Polls"):
    """Polls & Scheduling cog — interactive polls with scheduling and reaction voting."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._close_tasks: dict[int, asyncio.Task] = {}
        self._post_tasks: dict[int, asyncio.Task] = {}
        self._weekly_tasks: dict[int, asyncio.Task] = {}

    async def cog_load(self) -> None:
        """Re-arm close tasks for all active polls and weekly tasks for recurring polls."""
        now = datetime.now(timezone.utc)

        async with get_db() as db:
            cursor = await db.execute(SELECT_ACTIVE_POLLS)
            active_rows = await cursor.fetchall()

            cursor = await db.execute(SELECT_ACTIVE_RECURRING_POLLS)
            recurring_rows = await cursor.fetchall()

        for row in active_rows:
            try:
                close_at_raw = row["close_at"]
                if close_at_raw:
                    close_at = datetime.fromisoformat(str(close_at_raw))
                    if close_at.tzinfo is None:
                        close_at = close_at.replace(tzinfo=timezone.utc)
                    # Only arm if poll has a discord_message_id (has been posted)
                    # Scheduled-but-not-yet-posted polls are handled by _post_tasks via restart
                    if row["discord_message_id"]:
                        task = asyncio.create_task(
                            self._run_close_at(row["id"], close_at)
                        )
                        self._close_tasks[row["id"]] = task
            except (ValueError, TypeError) as exc:
                logger.warning("PollsCog: could not re-arm poll id=%s: %s", row["id"], exc)

        for row in recurring_rows:
            task = asyncio.create_task(self._run_weekly_post_task(row["id"]))
            self._weekly_tasks[row["id"]] = task

        logger.info(
            "PollsCog: re-armed %d close task(s) and %d weekly task(s)",
            len(self._close_tasks),
            len(self._weekly_tasks),
        )

    async def cog_unload(self) -> None:
        """Cancel all background tasks on unload."""
        for task in self._close_tasks.values():
            task.cancel()
        for task in self._post_tasks.values():
            task.cancel()
        for task in self._weekly_tasks.values():
            task.cancel()

    # ------------------------------------------------------------------ #
    # Slash command group                                                  #
    # ------------------------------------------------------------------ #

    poll = app_commands.Group(name="poll", description="Poll commands")

    # ------------------------------------------------------------------ #
    # /poll create                                                         #
    # ------------------------------------------------------------------ #

    @poll.command(name="create", description="Create a poll that closes after a set duration")
    @app_commands.describe(
        question="The poll question",
        options="Comma-separated options (2-9)",
        duration="How long to run: e.g. 30m, 2h, 1d",
        channel="Channel to post in (defaults to current channel)",
        max_choices="Max options a user may pick (requires Manage Guild)",
    )
    async def poll_create(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        duration: str,
        channel: Optional[discord.TextChannel] = None,
        max_choices: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        # Permission check for max_choices
        if max_choices is not None and not _has_manage_guild(interaction):
            await interaction.followup.send(
                "max_choices requires Manage Guild permission.", ephemeral=True
            )
            return

        # Parse options
        option_list = [o.strip() for o in options.split(",") if o.strip()]
        if len(option_list) < 2 or len(option_list) > 9:
            await interaction.followup.send(
                "Please provide between 2 and 9 options.", ephemeral=True
            )
            return

        # Parse duration
        delta = _parse_duration(duration)
        if delta is None:
            await interaction.followup.send(
                "Invalid duration. Use format: 30m, 2h, 1d", ephemeral=True
            )
            return

        close_at = datetime.now(timezone.utc) + delta
        target_channel = channel or interaction.channel

        # Insert poll row
        async with get_db() as db:
            cursor = await db.execute(
                INSERT_POLL,
                (
                    question,
                    json.dumps(option_list),
                    target_channel.id,
                    max_choices,
                    None,  # post_at
                    close_at.isoformat(),
                    None,  # recurring_poll_id
                ),
            )
            poll_id = cursor.lastrowid

        # Post embed and add reactions
        embed = _build_poll_embed(poll_id, question, option_list, close_at, max_choices=max_choices)
        msg = await target_channel.send(embed=embed)
        for i in range(len(option_list)):
            await msg.add_reaction(_OPTION_EMOJIS[i])

        # Record message ID
        async with get_db() as db:
            await db.execute(UPDATE_POLL_MESSAGE_ID, (str(msg.id), poll_id))

        # Schedule close task
        task = asyncio.create_task(self._run_close_at(poll_id, close_at))
        self._close_tasks[poll_id] = task

        await interaction.followup.send("Poll posted!", ephemeral=True)
        logger.info("PollsCog: created poll id=%d close_at=%s", poll_id, close_at)

    # ------------------------------------------------------------------ #
    # /poll schedule                                                       #
    # ------------------------------------------------------------------ #

    @poll.command(name="schedule", description="Schedule a poll to post at a future time")
    @app_commands.describe(
        question="The poll question",
        options="Comma-separated options (2-9)",
        post_at="When to post: e.g. '2026-04-06 09:00' or 'Friday 9:00am'",
        close_at="When to close: e.g. '2026-04-06 18:00' or 'Friday 6:00pm'",
        channel="Channel to post in (defaults to current channel)",
        max_choices="Max options a user may pick (requires Manage Guild)",
        repeat="Set to 'weekly' to make this a recurring weekly poll",
    )
    async def poll_schedule(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        post_at: str,
        close_at: str,
        channel: Optional[discord.TextChannel] = None,
        max_choices: Optional[int] = None,
        repeat: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if max_choices is not None and not _has_manage_guild(interaction):
            await interaction.followup.send(
                "max_choices requires Manage Guild permission.", ephemeral=True
            )
            return

        option_list = [o.strip() for o in options.split(",") if o.strip()]
        if len(option_list) < 2 or len(option_list) > 9:
            await interaction.followup.send(
                "Please provide between 2 and 9 options.", ephemeral=True
            )
            return

        post_dt = _parse_datetime(post_at)
        close_dt = _parse_datetime(close_at)
        if post_dt is None or close_dt is None:
            await interaction.followup.send(
                "Could not parse post_at or close_at. Use 'YYYY-MM-DD HH:MM' or 'Weekday H:MMam/pm'.",
                ephemeral=True,
            )
            return

        now = datetime.now(timezone.utc)
        if post_dt <= now:
            await interaction.followup.send("post_at must be in the future.", ephemeral=True)
            return
        if close_dt <= post_dt:
            await interaction.followup.send("close_at must be after post_at.", ephemeral=True)
            return

        target_channel = channel or interaction.channel

        if repeat and repeat.lower() == "weekly":
            # Create recurring poll and schedule it
            async with get_db() as db:
                cursor = await db.execute(
                    INSERT_RECURRING_POLL,
                    (
                        question,
                        json.dumps(option_list),
                        target_channel.id,
                        max_choices,
                        post_dt.strftime("%A"),
                        post_dt.strftime("%H:%M"),
                        close_dt.strftime("%H:%M"),
                    ),
                )
                recurring_id = cursor.lastrowid

            task = asyncio.create_task(self._run_weekly_post_task(recurring_id))
            self._weekly_tasks[recurring_id] = task

            await interaction.followup.send(
                f"Weekly poll scheduled every {post_dt.strftime('%A')} at "
                f"{post_dt.strftime('%H:%M UTC')} closing at {close_dt.strftime('%H:%M UTC')}.",
                ephemeral=True,
            )
        else:
            # One-time scheduled poll
            async with get_db() as db:
                cursor = await db.execute(
                    INSERT_POLL,
                    (
                        question,
                        json.dumps(option_list),
                        target_channel.id,
                        max_choices,
                        post_dt.isoformat(),
                        close_dt.isoformat(),
                        None,
                    ),
                )
                poll_id = cursor.lastrowid

            task = asyncio.create_task(
                self._run_post_then_close_task(poll_id, post_dt, close_dt)
            )
            self._post_tasks[poll_id] = task

            await interaction.followup.send(
                f"Poll scheduled to post at {post_dt.strftime('%Y-%m-%d %H:%M UTC')} "
                f"and close at {close_dt.strftime('%Y-%m-%d %H:%M UTC')}.",
                ephemeral=True,
            )
        logger.info("PollsCog: scheduled poll/recurring for post_at=%s close_at=%s", post_dt, close_dt)

    # ------------------------------------------------------------------ #
    # /poll schedule_weekly                                               #
    # ------------------------------------------------------------------ #

    @poll.command(name="schedule_weekly", description="Create a recurring weekly poll")
    @app_commands.describe(
        question="The poll question",
        options="Comma-separated options (2-9)",
        day="Day of the week to post (e.g. Monday)",
        post_time="Time to post in HH:MM 24h format (UTC), e.g. 09:00",
        close_time="Time to close in HH:MM 24h format (UTC), e.g. 18:00",
        channel="Channel to post in (defaults to current channel)",
        max_choices="Max options a user may pick (requires Manage Guild)",
    )
    async def poll_schedule_weekly(
        self,
        interaction: discord.Interaction,
        question: str,
        options: str,
        day: str,
        post_time: str,
        close_time: str,
        channel: Optional[discord.TextChannel] = None,
        max_choices: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if max_choices is not None and not _has_manage_guild(interaction):
            await interaction.followup.send(
                "max_choices requires Manage Guild permission.", ephemeral=True
            )
            return

        option_list = [o.strip() for o in options.split(",") if o.strip()]
        if len(option_list) < 2 or len(option_list) > 9:
            await interaction.followup.send(
                "Please provide between 2 and 9 options.", ephemeral=True
            )
            return

        if day.lower() not in _WEEKDAY_MAP:
            await interaction.followup.send(
                "Invalid day. Use a full weekday name e.g. Monday, Tuesday.", ephemeral=True
            )
            return

        # Validate time formats
        try:
            datetime.strptime(post_time, "%H:%M")
            datetime.strptime(close_time, "%H:%M")
        except ValueError:
            await interaction.followup.send(
                "Invalid time format. Use HH:MM (24h), e.g. 09:00.", ephemeral=True
            )
            return

        target_channel = channel or interaction.channel

        async with get_db() as db:
            cursor = await db.execute(
                INSERT_RECURRING_POLL,
                (
                    question,
                    json.dumps(option_list),
                    target_channel.id,
                    max_choices,
                    day.capitalize(),
                    post_time,
                    close_time,
                ),
            )
            recurring_id = cursor.lastrowid

        task = asyncio.create_task(self._run_weekly_post_task(recurring_id))
        self._weekly_tasks[recurring_id] = task

        await interaction.followup.send(
            f"Weekly poll scheduled for every {day.capitalize()} at {post_time} UTC.",
            ephemeral=True,
        )
        logger.info(
            "PollsCog: created recurring poll id=%d day=%s post_time=%s close_time=%s",
            recurring_id, day, post_time, close_time,
        )

    # ------------------------------------------------------------------ #
    # /poll results                                                        #
    # ------------------------------------------------------------------ #

    @poll.command(name="results", description="Show live vote counts for a poll")
    @app_commands.describe(poll_id="The ID of the poll")
    async def poll_results(
        self, interaction: discord.Interaction, poll_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
            poll_row = await cursor.fetchone()

        if not poll_row:
            await interaction.followup.send(f"Poll ID {poll_id} not found.", ephemeral=True)
            return

        async with get_db() as db:
            cursor = await db.execute(SELECT_VOTES_BY_POLL, (poll_id,))
            vote_rows = await cursor.fetchall()
            cursor = await db.execute(SELECT_DISTINCT_VOTERS, (poll_id,))
            voter_row = await cursor.fetchone()

        options = json.loads(poll_row["options"])
        vote_counts = {row["option_idx"]: row["cnt"] for row in vote_rows}
        distinct_voters = voter_row["cnt"] if voter_row else 0
        still_open = not bool(poll_row["closed"])

        embed = _build_results_embed(
            poll_id,
            poll_row["question"],
            options,
            vote_counts,
            distinct_voters,
            still_open=still_open,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ #
    # /poll close                                                          #
    # ------------------------------------------------------------------ #

    @poll.command(name="close", description="Close a poll and post the results summary")
    @app_commands.describe(poll_id="The ID of the poll to close")
    async def poll_close(
        self, interaction: discord.Interaction, poll_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
            poll_row = await cursor.fetchone()

        if not poll_row:
            await interaction.followup.send(f"Poll ID {poll_id} not found.", ephemeral=True)
            return

        if poll_row["closed"]:
            await interaction.followup.send("Poll already closed.", ephemeral=True)
            return

        await self._close_poll(poll_id)
        await interaction.followup.send("Poll closed.", ephemeral=True)

    # ------------------------------------------------------------------ #
    # /poll list                                                           #
    # ------------------------------------------------------------------ #

    @poll.command(name="list", description="List all active and scheduled polls")
    async def poll_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        async with get_db() as db:
            cursor = await db.execute(SELECT_ALL_POLLS_FOR_LIST)
            poll_rows = await cursor.fetchall()
            cursor = await db.execute(SELECT_ACTIVE_RECURRING_POLLS)
            recurring_rows = await cursor.fetchall()

        embed = discord.Embed(title="Active & Scheduled Polls", color=EMBED_COLOR)

        if not poll_rows and not recurring_rows:
            embed.description = "No active or scheduled polls."
        else:
            for row in poll_rows:
                q = str(row["question"])[:50]
                status = "Scheduled" if row["post_at"] else "Active"
                time_label = row["post_at"] if row["post_at"] else row["close_at"]
                recur_icon = " 🔁" if row["recurring_poll_id"] else ""
                embed.add_field(
                    name=f"ID {row['id']}{recur_icon} — {status}",
                    value=f"{q}\n{'Posts' if row['post_at'] else 'Closes'}: {time_label}",
                    inline=False,
                )

            for row in recurring_rows:
                # Show only if there is no open poll instance (avoid duplicates)
                q = str(row["question"])[:50]
                embed.add_field(
                    name=f"Recurring ID {row['id']} 🔁",
                    value=f"{q}\nEvery {row['day_of_week']} at {row['post_time']} (closes {row['close_time']})",
                    inline=False,
                )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ #
    # /poll cancel                                                         #
    # ------------------------------------------------------------------ #

    @poll.command(name="cancel", description="Cancel a poll or recurring poll series (Manage Guild)")
    @app_commands.describe(poll_id="The ID of the poll to cancel")
    async def poll_cancel(
        self, interaction: discord.Interaction, poll_id: int
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not _has_manage_guild(interaction):
            await interaction.followup.send(
                "Cancelling polls requires Manage Guild permission.", ephemeral=True
            )
            return

        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
            poll_row = await cursor.fetchone()

        if not poll_row:
            await interaction.followup.send(f"Poll ID {poll_id} not found.", ephemeral=True)
            return

        # Cancel associated asyncio tasks
        if poll_id in self._close_tasks:
            self._close_tasks[poll_id].cancel()
            del self._close_tasks[poll_id]
        if poll_id in self._post_tasks:
            self._post_tasks[poll_id].cancel()
            del self._post_tasks[poll_id]

        # If recurring: deactivate recurring series and cancel weekly task
        recurring_id = poll_row["recurring_poll_id"]
        if recurring_id:
            async with get_db() as db:
                await db.execute(DEACTIVATE_RECURRING_POLL, (recurring_id,))
            if recurring_id in self._weekly_tasks:
                self._weekly_tasks[recurring_id].cancel()
                del self._weekly_tasks[recurring_id]

        # Mark poll closed (without posting results summary)
        async with get_db() as db:
            await db.execute(CLOSE_POLL, (poll_id,))

        await interaction.followup.send("Poll cancelled.", ephemeral=True)
        logger.info("PollsCog: cancelled poll id=%d by %s", poll_id, interaction.user)

    # ------------------------------------------------------------------ #
    # /poll edit_recurring                                                 #
    # ------------------------------------------------------------------ #

    @poll.command(name="edit_recurring", description="Update a recurring poll's schedule (Manage Guild)")
    @app_commands.describe(
        poll_id="The poll ID (must be a recurring poll)",
        question="New question (optional)",
        options="New comma-separated options (optional)",
        day="New day of the week (optional)",
        post_time="New post time HH:MM UTC (optional)",
        close_time="New close time HH:MM UTC (optional)",
        max_choices="New max choices (optional, requires Manage Guild)",
    )
    async def poll_edit_recurring(
        self,
        interaction: discord.Interaction,
        poll_id: int,
        question: Optional[str] = None,
        options: Optional[str] = None,
        day: Optional[str] = None,
        post_time: Optional[str] = None,
        close_time: Optional[str] = None,
        max_choices: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not _has_manage_guild(interaction):
            await interaction.followup.send(
                "Editing recurring polls requires Manage Guild permission.", ephemeral=True
            )
            return

        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
            poll_row = await cursor.fetchone()

        if not poll_row:
            await interaction.followup.send(f"Poll ID {poll_id} not found.", ephemeral=True)
            return

        recurring_id = poll_row["recurring_poll_id"]
        if not recurring_id:
            await interaction.followup.send("Not a recurring poll.", ephemeral=True)
            return

        # Validate day if provided
        if day is not None and day.lower() not in _WEEKDAY_MAP:
            await interaction.followup.send(
                "Invalid day. Use a full weekday name e.g. Monday, Tuesday.", ephemeral=True
            )
            return

        options_json = json.dumps([o.strip() for o in options.split(",") if o.strip()]) if options else None
        day_normalized = day.capitalize() if day else None

        async with get_db() as db:
            await db.execute(
                UPDATE_RECURRING_POLL,
                (question, options_json, day_normalized, post_time, close_time, max_choices, recurring_id),
            )

        await interaction.followup.send(
            "Recurring poll updated — changes take effect on next occurrence.", ephemeral=True
        )
        logger.info("PollsCog: updated recurring poll id=%d by %s", recurring_id, interaction.user)

    # ------------------------------------------------------------------ #
    # Background tasks                                                     #
    # ------------------------------------------------------------------ #

    async def _run_close_at(self, poll_id: int, close_at: datetime) -> None:
        """Sleep until close_at then close the poll."""
        now = datetime.now(timezone.utc)
        delay = max(0.0, (close_at - now).total_seconds())
        try:
            await asyncio.sleep(delay)
            await self._close_poll(poll_id)
        except asyncio.CancelledError:
            pass
        finally:
            self._close_tasks.pop(poll_id, None)

    async def _run_post_then_close_task(
        self, poll_id: int, post_at: datetime, close_at: datetime
    ) -> None:
        """Sleep until post_at, post the poll, then sleep until close_at and close it."""
        now = datetime.now(timezone.utc)
        post_delay = max(0.0, (post_at - now).total_seconds())
        try:
            await asyncio.sleep(post_delay)

            # Fetch poll row
            async with get_db() as db:
                cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
                poll_row = await cursor.fetchone()

            if not poll_row or poll_row["closed"]:
                return

            options = json.loads(poll_row["options"])
            target_channel = self.bot.get_channel(int(poll_row["channel_id"]))
            if not target_channel:
                logger.warning("PollsCog: scheduled poll id=%d — channel not found", poll_id)
                return

            embed = _build_poll_embed(
                poll_id,
                poll_row["question"],
                options,
                close_at,
                max_choices=poll_row["max_choices"],
            )
            msg = await target_channel.send(embed=embed)
            for i in range(len(options)):
                await msg.add_reaction(_OPTION_EMOJIS[i])

            async with get_db() as db:
                await db.execute(UPDATE_POLL_MESSAGE_ID, (str(msg.id), poll_id))

            # Now wait until close_at
            close_delay = max(0.0, (close_at - datetime.now(timezone.utc)).total_seconds())
            await asyncio.sleep(close_delay)
            await self._close_poll(poll_id)

        except asyncio.CancelledError:
            pass
        finally:
            self._post_tasks.pop(poll_id, None)

    async def _run_weekly_post_task(self, recurring_id: int) -> None:
        """Indefinitely post and close weekly poll instances for a recurring poll."""
        while True:
            try:
                async with get_db() as db:
                    cursor = await db.execute(SELECT_RECURRING_POLL_BY_ID, (recurring_id,))
                    rec_row = await cursor.fetchone()

                if not rec_row or not rec_row["active"]:
                    break

                day_of_week = rec_row["day_of_week"]
                post_time_str = rec_row["post_time"]
                close_time_str = rec_row["close_time"]

                # Compute next post_at and close_at
                post_at = _next_weekday_at(day_of_week, post_time_str)
                close_hour, close_minute = map(int, close_time_str.split(":"))
                close_at = post_at.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
                if close_at <= post_at:
                    close_at += timedelta(weeks=1)

                now = datetime.now(timezone.utc)

                # If we missed this week's window (offline during the slot), post immediately
                if now > close_at:
                    post_at = now
                    close_at = now + timedelta(seconds=1)  # close immediately after posting

                post_delay = max(0.0, (post_at - now).total_seconds())
                await asyncio.sleep(post_delay)

                # Re-check active after sleep
                async with get_db() as db:
                    cursor = await db.execute(SELECT_RECURRING_POLL_BY_ID, (recurring_id,))
                    rec_row = await cursor.fetchone()
                if not rec_row or not rec_row["active"]:
                    break

                options = json.loads(rec_row["options"])
                target_channel = self.bot.get_channel(int(rec_row["channel_id"]))
                if not target_channel:
                    logger.warning(
                        "PollsCog: weekly task recurring_id=%d — channel not found", recurring_id
                    )
                    await asyncio.sleep(3600)  # Retry next hour
                    continue

                # Insert a new poll instance
                async with get_db() as db:
                    cursor = await db.execute(
                        INSERT_POLL,
                        (
                            rec_row["question"],
                            rec_row["options"],
                            rec_row["channel_id"],
                            rec_row["max_choices"],
                            None,  # post_at — posted immediately
                            close_at.isoformat(),
                            recurring_id,
                        ),
                    )
                    new_poll_id = cursor.lastrowid

                embed = _build_poll_embed(
                    new_poll_id,
                    rec_row["question"],
                    options,
                    close_at,
                    max_choices=rec_row["max_choices"],
                    recurring_day=day_of_week,
                    post_time=post_time_str,
                )
                msg = await target_channel.send(embed=embed)
                for i in range(len(options)):
                    await msg.add_reaction(_OPTION_EMOJIS[i])

                async with get_db() as db:
                    await db.execute(UPDATE_POLL_MESSAGE_ID, (str(msg.id), new_poll_id))

                logger.info(
                    "PollsCog: weekly recurring_id=%d — posted poll id=%d", recurring_id, new_poll_id
                )

                # Sleep until close
                close_delay = max(0.0, (close_at - datetime.now(timezone.utc)).total_seconds())
                await asyncio.sleep(close_delay)
                await self._close_poll(new_poll_id)

                # Loop again for next week
                await asyncio.sleep(60)  # Small pause before re-checking

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception(
                    "PollsCog: weekly task recurring_id=%d error: %s", recurring_id, exc
                )
                await asyncio.sleep(300)  # Back off 5 min on unexpected error

    async def _close_poll(self, poll_id: int) -> None:
        """Mark poll closed, fetch results, and post results summary to the channel."""
        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_ID, (poll_id,))
            poll_row = await cursor.fetchone()

        if not poll_row:
            return
        if poll_row["closed"]:
            return

        # Mark closed first
        async with get_db() as db:
            await db.execute(CLOSE_POLL, (poll_id,))

        # Fetch votes
        async with get_db() as db:
            cursor = await db.execute(SELECT_VOTES_BY_POLL, (poll_id,))
            vote_rows = await cursor.fetchall()
            cursor = await db.execute(SELECT_DISTINCT_VOTERS, (poll_id,))
            voter_row = await cursor.fetchone()

        options = json.loads(poll_row["options"])
        vote_counts = {row["option_idx"]: row["cnt"] for row in vote_rows}
        distinct_voters = voter_row["cnt"] if voter_row else 0

        # Check recurring info for next occurrence display
        recurring_day = None
        rec_post_time = None
        recurring_id = poll_row["recurring_poll_id"]
        if recurring_id:
            async with get_db() as db:
                cursor = await db.execute(SELECT_RECURRING_POLL_BY_ID, (recurring_id,))
                rec_row = await cursor.fetchone()
            if rec_row and rec_row["active"]:
                recurring_day = rec_row["day_of_week"]
                rec_post_time = rec_row["post_time"]
                logger.info(
                    "PollsCog: poll id=%d closed — next instance posted by weekly task", poll_id
                )

        embed = _build_results_embed(
            poll_id,
            poll_row["question"],
            options,
            vote_counts,
            distinct_voters,
            recurring_day=recurring_day,
            post_time=rec_post_time,
        )

        # Try to edit original message and send follow-up results
        channel_id = poll_row["channel_id"]
        discord_message_id = poll_row["discord_message_id"]
        channel = self.bot.get_channel(int(channel_id)) if channel_id else None

        if channel and discord_message_id:
            try:
                original_msg = await channel.fetch_message(int(discord_message_id))
                closed_embed = discord.Embed(
                    title=f"📊 {poll_row['question']} [CLOSED]",
                    color=EMBED_COLOR,
                    description="This poll is now closed.",
                )
                await original_msg.edit(embed=closed_embed)
            except discord.NotFound:
                pass
            except Exception as exc:
                logger.warning("PollsCog: could not edit original poll message: %s", exc)
            await channel.send(embed=embed)

        logger.info(
            "PollsCog: closed poll id=%d — %d vote(s) from %d voter(s)",
            poll_id, sum(vote_counts.values()), distinct_voters,
        )

    # ------------------------------------------------------------------ #
    # Reaction handler — vote enforcement                                 #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Enforce vote limits on poll messages.

        Handles three modes:
          - Unlimited (max_choices=None): always allow
          - Radio button (max_choices=1): swap to new choice
          - Max-N (max_choices>1): remove reaction if limit exceeded
        """
        # 1. Ignore bot reactions
        if payload.member is None or payload.member.bot:
            return

        # 2. Only handle poll option emojis
        emoji_name = payload.emoji.name
        if emoji_name not in _EMOJI_TO_IDX:
            return

        option_idx = _EMOJI_TO_IDX[emoji_name]

        # 3. Fetch the channel and look up poll by message ID
        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return

        async with get_db() as db:
            cursor = await db.execute(SELECT_POLL_BY_MESSAGE_ID, (str(payload.message_id),))
            poll_row = await cursor.fetchone()

        # 4. Not a poll message or poll is closed — remove reaction
        if not poll_row or poll_row["closed"]:
            try:
                msg = await channel.fetch_message(payload.message_id)
                await msg.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
            except Exception:
                pass
            return

        options = json.loads(poll_row["options"])
        poll_id = poll_row["id"]
        max_choices = poll_row["max_choices"]
        user_id = str(payload.user_id)

        # 5. Validate option index is in range
        if option_idx >= len(options):
            try:
                msg = await channel.fetch_message(payload.message_id)
                await msg.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
            except Exception:
                pass
            return

        # 6. Unlimited voting — just record
        if max_choices is None:
            async with get_db() as db:
                await db.execute(INSERT_POLL_VOTE, (poll_id, user_id, option_idx))
            return

        # 7. Radio button (max_choices == 1)
        if max_choices == 1:
            async with get_db() as db:
                cursor = await db.execute(SELECT_VOTES_BY_USER, (poll_id, user_id))
                existing_votes = await cursor.fetchall()

            current_idxs = [row["option_idx"] for row in existing_votes]

            if option_idx in current_idxs:
                # Already voted for this option — no-op (reaction stays)
                return

            # Remove old vote and reaction, then insert new
            if current_idxs:
                old_idx = current_idxs[0]
                async with get_db() as db:
                    await db.execute(DELETE_POLL_VOTE, (poll_id, user_id, old_idx))
                try:
                    msg = await channel.fetch_message(payload.message_id)
                    old_emoji = _OPTION_EMOJIS[old_idx]
                    await msg.remove_reaction(old_emoji, discord.Object(id=payload.user_id))
                except Exception as exc:
                    logger.warning("PollsCog: could not remove old reaction: %s", exc)

            async with get_db() as db:
                await db.execute(INSERT_POLL_VOTE, (poll_id, user_id, option_idx))
            return

        # 8. Max-N mode
        async with get_db() as db:
            cursor = await db.execute(SELECT_VOTE_COUNT_BY_USER, (poll_id, user_id))
            count_row = await cursor.fetchone()
        current_count = count_row["cnt"] if count_row else 0

        if current_count >= max_choices:
            # Remove the new reaction and warn user
            try:
                msg = await channel.fetch_message(payload.message_id)
                await msg.remove_reaction(payload.emoji, discord.Object(id=payload.user_id))
            except Exception as exc:
                logger.warning("PollsCog: could not remove excess reaction: %s", exc)
            await channel.send(
                f"<@{payload.user_id}> You can only pick {max_choices} option(s) in this poll. "
                "Remove one of your current votes first.",
                delete_after=10,
            )
            return

        async with get_db() as db:
            await db.execute(INSERT_POLL_VOTE, (poll_id, user_id, option_idx))


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook. Guild sync is handled centrally in bot.py on_ready."""
    cog = PollsCog(bot)
    await bot.add_cog(cog)
