"""
NBA parlay AI cog for chewyBot.

Uses balldontlie API (no key) for team stats and recent results.
Reuses The Odds API adapter (adapters/odds_api.py) for NBA lines.
Daily auto-post at PARLAY_POST_TIME (default 11:00 AM ET) to PARLAY_CHANNEL_ID.
Self-learning: Discord reactions (✅/❌) update factor weights stored in DB.
Slash commands: /parlay, /parlay_stats, /parlay_history

Full implementation: Phase 4.
Requirement: PAR-01 through PAR-08
"""
from __future__ import annotations

import discord
from discord.ext import commands


class ParlayCog(commands.Cog, name="Parlay"):
    """NBA parlay AI cog — self-learning from reaction feedback. Full implementation in Phase 4."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        pass


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(ParlayCog(bot))
