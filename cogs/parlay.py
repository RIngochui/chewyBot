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
from datetime import datetime, timezone
import zoneinfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import config, EMBED_COLOR
from database.db import get_db
from database.queries import (
    INSERT_PARLAY,
    UPDATE_PARLAY_MESSAGE_ID,
    INSERT_PARLAY_LEG,
    SEED_LEG_TYPE_WEIGHTS,
    SELECT_ALL_LEG_TYPE_WEIGHTS,
    SELECT_LATEST_PARLAYS,
    SELECT_PARLAY_STATS,
    SELECT_PARLAY_WITH_LEGS,
)
from models.parlay import Parlay
from services.parlay_engine import generate_parlay, resolve_pending_parlays
from utils.formatters import build_parlay_embed, build_parlay_result_embed

logger = logging.getLogger(__name__)

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

        # Auto-resolve stale pending parlays before posting today's parlay
        resolved = await resolve_pending_parlays()
        for result in resolved:
            if result["outcome"] != "pending":
                result_embed = build_parlay_result_embed(result)
                await channel.send(embed=result_embed)

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


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook. Guild sync is handled centrally in bot.py on_ready."""
    cog = ParlayCog(bot)
    await bot.add_cog(cog)
