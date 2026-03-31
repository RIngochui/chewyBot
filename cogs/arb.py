"""
Sports arbitrage and +EV scanner cog for chewyBot.

Uses adapter pattern (adapters/odds_api.py) to fetch odds from The Odds API.
MOCK_MODE=true loads from mock/odds_api_sample.json instead of live API.
Auto-scanner loop runs every SCAN_INTERVAL_SECONDS, posts alerts to ARB_CHANNEL_ID.
Slash commands: /ping, /scan, /latest_arbs, /latest_ev, /set_bankroll,
                /set_min_arb, /set_min_ev, /toggle_sport, /status

Full implementation: Phase 3.
Requirement: ARB-01 through ARB-09
"""
from __future__ import annotations

import discord
from discord.ext import commands


class ArbCog(commands.Cog, name="Arbitrage"):
    """Arbitrage scanner cog — The Odds API powered arb/EV detection. Full implementation in Phase 3."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        pass


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(ArbCog(bot))
