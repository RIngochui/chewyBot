"""
NBA parlay AI cog for chewyBot.

Implements the user-facing layer of the NBA Parlay AI (Phase 4):
  - Auto-posts daily parlay at PARLAY_POST_TIME (ET) to PARLAY_CHANNEL_ID (PAR-02)
  - No-games fallback: logs to LOG_CHANNEL_ID, nothing posted to PARLAY_CHANNEL_ID
  - Persists every posted parlay to DB with all legs and discord_message_id (PAR-05)
  - Seeds leg_type_weights for all 6 leg types on cog_load (PAR-09)
  - /parlay    — manually generate and post today's parlay (PAR-11)
  - /parlay_stats — hit rate, total tracked, best/worst leg types (PAR-12)
  - /parlay_history [n] — last n parlays with outcome (PAR-13)

All SQL goes through database/queries.py constants — zero inline SQL here.
References: PAR-02, PAR-05, PAR-09, PAR-11, PAR-12, PAR-13
"""
from __future__ import annotations

import datetime as _dt
import logging
from datetime import datetime, timedelta, timezone
import zoneinfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import config, EMBED_COLOR
from database.db import get_db
from database.queries import (
    INSERT_PARLAY,
    UPDATE_PARLAY_MESSAGE_ID,
    UPDATE_PARLAY_OUTCOME,
    INSERT_PARLAY_LEG,
    SEED_LEG_TYPE_WEIGHTS,
    SELECT_ALL_LEG_TYPE_WEIGHTS,
    SELECT_LATEST_PARLAYS,
    SELECT_PARLAY_STATS,
    SELECT_PARLAY_WITH_LEGS,
    SELECT_PARLAY_BY_MESSAGE_ID,
    SELECT_PARLAY_LEGS,
    SELECT_PARLAY_LEGS_ORDERED,
    UPDATE_PARLAY_LEG_OUTCOME,
    SELECT_LEG_TYPE_WEIGHT,
    UPSERT_LEG_TYPE_WEIGHT_HIT,
    UPSERT_LEG_TYPE_WEIGHT_MISS,
)
from models.parlay import Parlay
from services.parlay_engine import generate_parlay
from utils.formatters import build_parlay_embed

logger = logging.getLogger(__name__)

# Number emoji for per-leg reaction feedback (1️⃣ through 5️⃣)
# Parlays are capped at 5 legs, so this list covers all valid cases.
_NUMBER_EMOJIS: list[str] = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

# Maps Discord number keycap emoji name to 1-based leg index.
# Discord sends keycap emoji with (U+FE0F variation selector) or without (U+20E3 only).
# Both variants are included to handle both cases reliably.
_LEG_EMOJI_MAP: dict[str, int] = {
    "1️⃣": 1, "1\u20e3": 1,
    "2️⃣": 2, "2\u20e3": 2,
    "3️⃣": 3, "3\u20e3": 3,
    "4️⃣": 4, "4\u20e3": 4,
    "5️⃣": 5, "5\u20e3": 5,
}

# All 6 locked leg types from CONTEXT.md Decision A
_ALL_LEG_TYPES: list[str] = [
    "h2h_favorite",
    "h2h_underdog",
    "spread_home",
    "spread_away",
    "totals_over",
    "totals_under",
]


class ParlayCog(commands.Cog, name="Parlay"):
    """NBA parlay AI cog — daily auto-post, self-learning from reaction feedback.

    Delegates all generation logic to services/parlay_engine.py.
    Delegates all embed formatting to utils/formatters.py.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Parse PARLAY_POST_TIME and apply ET timezone (CONTEXT.md Decision E)
        hour, minute = map(int, config.PARLAY_POST_TIME.split(":"))
        try:
            tz = zoneinfo.ZoneInfo("America/New_York")
        except Exception:
            # Fallback to UTC if zoneinfo is unavailable (should not happen on Python 3.9+)
            logger.warning("ParlayCog: zoneinfo not available, falling back to UTC for post time")
            tz = timezone.utc  # type: ignore[assignment]
        post_time = _dt.time(hour=hour, minute=minute, tzinfo=tz)
        self.daily_parlay.change_interval(time=[post_time])

    async def cog_load(self) -> None:
        """Seed leg_type_weights for all 6 leg types and start the daily loop. PAR-09.

        SEED_LEG_TYPE_WEIGHTS uses ON CONFLICT DO NOTHING so existing rows are
        preserved — weights learned from reactions survive bot restarts.
        """
        async with get_db() as db:
            for leg_type in _ALL_LEG_TYPES:
                await db.execute(SEED_LEG_TYPE_WEIGHTS, (leg_type,))
        logger.info("ParlayCog: leg_type_weights seeded for all 6 leg types")
        self.daily_parlay.start()

    async def cog_unload(self) -> None:
        """Cancel the daily task on unload."""
        self.daily_parlay.cancel()

    # ------------------------------------------------------------------ #
    # Background task — daily parlay post                                 #
    # ------------------------------------------------------------------ #

    @tasks.loop(time=_dt.time(hour=16, minute=0, tzinfo=_dt.timezone.utc))
    async def daily_parlay(self) -> None:
        """Auto-post today's NBA parlay at PARLAY_POST_TIME (ET). PAR-02.

        No-games fallback (CONTEXT.md Decision B):
          - If generate_parlay() returns None, log to LOG_CHANNEL_ID and return.
          - Nothing is posted to PARLAY_CHANNEL_ID on fallback.
        """
        channel = self.bot.get_channel(config.PARLAY_CHANNEL_ID)
        if not channel:
            logger.warning(
                "ParlayCog: daily_parlay — PARLAY_CHANNEL_ID=%d channel not found",
                config.PARLAY_CHANNEL_ID,
            )
            return

        parlay = await generate_parlay(min_leg_score=config.MIN_LEG_SCORE)

        if parlay is None:
            # No-games fallback: log to LOG_CHANNEL_ID only (Decision B)
            log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if log_channel:
                await log_channel.send(
                    "[Parlay] Skipped daily post — fewer than 3 scoreable legs found"
                )
            logger.info("ParlayCog: daily post skipped — no scoreable legs")
            return

        await self._post_and_save_parlay(channel, parlay)

    @daily_parlay.before_loop
    async def before_daily_parlay(self) -> None:
        """Wait until the bot is fully ready before the task can fire."""
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Private helper                                                      #
    # ------------------------------------------------------------------ #

    async def _post_and_save_parlay(
        self,
        channel: discord.abc.Messageable,
        parlay: Parlay,
    ) -> None:
        """Post the parlay embed to channel and persist to DB with legs and message_id. PAR-05."""
        post_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        embed = build_parlay_embed(parlay, post_date)
        msg = await channel.send(embed=embed)

        # Add number reactions for per-leg feedback (one per leg, 1️⃣ through N️⃣)
        for i in range(min(len(parlay.legs), 5)):
            await msg.add_reaction(_NUMBER_EMOJIS[i])

        async with get_db() as db:
            # Insert the parlay row
            cursor = await db.execute(
                INSERT_PARLAY,
                (
                    parlay.combined_odds,
                    parlay.confidence_score,
                    len(parlay.legs),
                    parlay.generated_at.isoformat(),
                ),
            )
            parlay_id = cursor.lastrowid

            # Immediately record the Discord message_id so reaction handler
            # can look up the parlay from the reaction event (Plan 04)
            await db.execute(UPDATE_PARLAY_MESSAGE_ID, (str(msg.id), parlay_id))

            # Insert each individual leg
            for leg in parlay.legs:
                await db.execute(
                    INSERT_PARLAY_LEG,
                    (
                        parlay_id,
                        leg.team,
                        leg.market_type,
                        leg.line_value,
                        leg.american_odds,
                        leg.leg_score,
                        leg.leg_type,
                    ),
                )

        logger.info(
            "ParlayCog: posted parlay id=%d message_id=%s legs=%d confidence=%.1f",
            parlay_id,
            msg.id,
            len(parlay.legs),
            parlay.confidence_score,
        )

    # ------------------------------------------------------------------ #
    # Slash commands                                                      #
    # ------------------------------------------------------------------ #

    @app_commands.command(name="parlay", description="Generate today's NBA parlay")
    async def parlay_cmd(self, interaction: discord.Interaction) -> None:
        """Manually generate and post today's NBA parlay to PARLAY_CHANNEL_ID. PAR-11."""
        await interaction.response.defer(ephemeral=False)
        parlay = await generate_parlay(min_leg_score=config.MIN_LEG_SCORE)
        if parlay is None:
            await interaction.followup.send(
                "No NBA parlay available today — fewer than 3 scoreable legs found."
            )
            return

        channel = self.bot.get_channel(config.PARLAY_CHANNEL_ID)
        if channel is None:
            await interaction.followup.send(
                "PARLAY_CHANNEL_ID channel not found — check bot config.",
                ephemeral=True,
            )
            return

        await self._post_and_save_parlay(channel, parlay)
        await interaction.followup.send(
            "Parlay posted to the parlay channel!", ephemeral=True
        )

    @app_commands.command(
        name="parlay_stats",
        description="Show NBA parlay AI performance stats",
    )
    async def parlay_stats(self, interaction: discord.Interaction) -> None:
        """Display overall hit rate, total parlays tracked, and per-leg-type breakdown. PAR-12."""
        await interaction.response.defer(ephemeral=True)

        async with get_db() as db:
            # Overall parlay stats (non-pending rows only)
            cursor = await db.execute(SELECT_PARLAY_STATS)
            stats_row = await cursor.fetchone()
            total_tracked: int = int(stats_row["total_tracked"]) if stats_row else 0
            total_hits: int = int(stats_row["total_hits"] or 0) if stats_row else 0
            total_misses: int = int(stats_row["total_misses"] or 0) if stats_row else 0

            # Per-leg-type weights and hit/miss counts
            cursor = await db.execute(SELECT_ALL_LEG_TYPE_WEIGHTS)
            weight_rows = await cursor.fetchall()

        hit_rate: float = (total_hits / total_tracked * 100) if total_tracked > 0 else 0.0

        def _leg_hit_rate(row: dict) -> float:
            h, m = int(row["hit_count"] or 0), int(row["miss_count"] or 0)
            return h / (h + m) if (h + m) > 0 else 0.0

        sorted_legs = sorted(weight_rows, key=_leg_hit_rate, reverse=True)
        best_leg = sorted_legs[0]["leg_type"] if sorted_legs else "N/A"
        worst_leg = sorted_legs[-1]["leg_type"] if sorted_legs else "N/A"

        embed = discord.Embed(title="Parlay AI Stats", color=EMBED_COLOR)
        embed.add_field(name="Total Tracked", value=str(total_tracked), inline=True)
        embed.add_field(name="Hit Rate", value=f"{hit_rate:.1f}%", inline=True)
        embed.add_field(
            name="Hits / Misses",
            value=f"{total_hits} / {total_misses}",
            inline=True,
        )
        embed.add_field(name="Best Leg Type", value=best_leg, inline=True)
        embed.add_field(name="Worst Leg Type", value=worst_leg, inline=True)

        # Per-leg-type breakdown
        breakdown_lines = [
            f"{r['leg_type']}: {_leg_hit_rate(r) * 100:.0f}% "
            f"({int(r['hit_count'] or 0)}H/{int(r['miss_count'] or 0)}M)"
            for r in sorted_legs
        ]
        if breakdown_lines:
            embed.add_field(
                name="Leg Type Breakdown",
                value="\n".join(breakdown_lines),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="parlay_history",
        description="Show recent parlay results",
    )
    @app_commands.describe(n="Number of parlays to show (default 5, max 10)")
    async def parlay_history(
        self, interaction: discord.Interaction, n: int = 5
    ) -> None:
        """Show the last n parlays with their outcomes, odds, and confidence. PAR-13."""
        await interaction.response.defer(ephemeral=True)
        # Clamp n to the 1-10 range to prevent abuse / oversized embeds
        n = min(max(1, n), 10)

        async with get_db() as db:
            cursor = await db.execute(SELECT_LATEST_PARLAYS, (n,))
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send(
                "No parlays tracked yet.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Parlay History (last {len(rows)})", color=EMBED_COLOR
        )
        _outcome_emoji: dict[str, str] = {"hit": "✅", "miss": "❌", "pending": "⏳"}

        for row in rows:
            outcome_str: str = row["outcome"] or "pending"
            emoji = _outcome_emoji.get(outcome_str, "?")
            combined_odds: float = float(row["combined_odds"])
            # combined_odds is stored as decimal; display as American if >=1 (parlay will always be >1)
            # For display, show as multiplier (e.g. 3.50x) since parlay odds are decimal
            odds_display = f"{combined_odds:.2f}x"
            embed.add_field(
                name=(
                    f"{str(row['generated_at'])[:10]} — "
                    f"{emoji} {outcome_str.upper()}"
                ),
                value=(
                    f"Legs: {row['leg_count']} | "
                    f"Odds: {odds_display} | "
                    f"Confidence: {float(row['confidence_score']):.0f}/100"
                ),
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------ #
    # Reaction handler — self-learning feedback loop (PAR-06, PAR-07, PAR-14) #
    # ------------------------------------------------------------------ #

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle ✅/❌ reactions on posted parlay messages. PAR-06, PAR-14.

        Enforces: bot reactions ignored, 24h window, first-reaction-wins (DB authoritative),
        PARLAY_CHANNEL_ID scope only. Updates leg_type_weights per PAR-07.
        """
        # 1. Ignore bot reactions (PAR-14)
        if payload.member is None or payload.member.bot:
            return

        # 2. Only react to messages in PARLAY_CHANNEL_ID
        if payload.channel_id != config.PARLAY_CHANNEL_ID:
            return

        # 3. Only ✅, ❌ or number keycap emoji (handle both unicode and name variants, PAR-14 / Pitfall 4)
        emoji_name = payload.emoji.name
        is_hit = emoji_name in ("✅", "white_check_mark")
        is_miss = emoji_name in ("❌", "x")
        is_leg_emoji = emoji_name in _LEG_EMOJI_MAP
        if not (is_hit or is_miss or is_leg_emoji):
            return

        # Branch A: ✅/❌ whole-parlay outcome handler
        if is_hit or is_miss:
            # 4. Look up parlay by message_id
            async with get_db() as db:
                cursor = await db.execute(SELECT_PARLAY_BY_MESSAGE_ID, (str(payload.message_id),))
                row = await cursor.fetchone()

            if not row:
                return  # Not a parlay message

            parlay_id = row["id"]
            generated_at_iso = row["generated_at"]
            current_outcome = row["outcome"]

            # 5. First-reaction-wins: skip if already scored (PAR-14, Decision D)
            # DB-authoritative — handles restarts correctly (no in-memory set needed)
            if current_outcome != "pending":
                return

            # 6. Enforce 24-hour window (PAR-14, Decision D)
            try:
                generated_at = datetime.fromisoformat(generated_at_iso)
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone.utc)
                if datetime.now(tz=timezone.utc) - generated_at > timedelta(hours=24):
                    return  # Reaction too late
            except (ValueError, TypeError):
                logger.warning(f"ParlayCog: could not parse generated_at for parlay {parlay_id}")
                return

            # 7. Determine outcome
            outcome = "hit" if is_hit else "miss"
            delta = 1 if is_hit else -1

            # 8. Update parlay outcome and leg_type_weights atomically (PAR-06, PAR-07)
            async with get_db() as db:
                # Mark parlay outcome first (prevents race condition on repeated rapid reactions)
                await db.execute(UPDATE_PARLAY_OUTCOME, (outcome, parlay_id))

                # Fetch legs for this parlay
                cursor = await db.execute(SELECT_PARLAY_LEGS, (parlay_id,))
                legs = await cursor.fetchall()

                for leg in legs:
                    leg_type = leg["leg_type"]

                    # Get current weight
                    w_cursor = await db.execute(SELECT_LEG_TYPE_WEIGHT, (leg_type,))
                    w_row = await w_cursor.fetchone()
                    old_weight = w_row["weight"] if w_row else 1.0

                    # Calculate new weight (PAR-07): new = old + (LEARNING_RATE * delta)
                    # Floor at 0.1 so weights never go to zero or negative
                    new_weight = max(0.1, old_weight + (config.PARLAY_LEARNING_RATE * delta))

                    # Upsert weight + increment appropriate counter
                    if is_hit:
                        await db.execute(UPSERT_LEG_TYPE_WEIGHT_HIT, (leg_type, new_weight))
                    else:
                        await db.execute(UPSERT_LEG_TYPE_WEIGHT_MISS, (leg_type, new_weight))

            logger.info(
                f"ParlayCog: parlay {parlay_id} marked {outcome.upper()} "
                f"by {payload.member} — weights updated for {len(legs)} legs"
            )
            return

        # Branch B: Per-leg reaction — number emoji marks a specific leg as miss
        if is_leg_emoji:
            leg_index = _LEG_EMOJI_MAP[emoji_name]  # 1-based

            async with get_db() as db:
                cursor = await db.execute(SELECT_PARLAY_BY_MESSAGE_ID, (str(payload.message_id),))
                row = await cursor.fetchone()

            if not row:
                return

            parlay_id = row["id"]
            generated_at_iso = row["generated_at"]

            # Enforce 24-hour window (same logic as whole-parlay handler)
            try:
                generated_at = datetime.fromisoformat(generated_at_iso)
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone.utc)
                if datetime.now(tz=timezone.utc) - generated_at > timedelta(hours=24):
                    return
            except (ValueError, TypeError):
                logger.warning(f"ParlayCog: could not parse generated_at for parlay {parlay_id}")
                return

            async with get_db() as db:
                cursor = await db.execute(SELECT_PARLAY_LEGS_ORDERED, (parlay_id,))
                legs = await cursor.fetchall()

            if leg_index > len(legs):
                return  # Reaction number exceeds this parlay's leg count

            target_leg = legs[leg_index - 1]  # Convert 1-based index to 0-based

            # Idempotency: skip if already scored (avoids double-counting weights)
            if target_leg["outcome"] != "pending":
                return

            leg_id = target_leg["id"]
            leg_type = target_leg["leg_type"]

            async with get_db() as db:
                # Mark this specific leg as miss
                await db.execute(UPDATE_PARLAY_LEG_OUTCOME, ("miss", leg_id))

                # Update leg_type_weight for this leg's type only
                w_cursor = await db.execute(SELECT_LEG_TYPE_WEIGHT, (leg_type,))
                w_row = await w_cursor.fetchone()
                old_weight = w_row["weight"] if w_row else 1.0
                new_weight = max(0.1, old_weight + (config.PARLAY_LEARNING_RATE * -1))
                await db.execute(UPSERT_LEG_TYPE_WEIGHT_MISS, (leg_type, new_weight))

            logger.info(
                f"ParlayCog: parlay {parlay_id} leg {leg_index} ({leg_type}) marked miss "
                f"by {payload.member} via {emoji_name} reaction"
            )
            return


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook. Guild sync is handled centrally in bot.py on_ready."""
    cog = ParlayCog(bot)
    await bot.add_cog(cog)
