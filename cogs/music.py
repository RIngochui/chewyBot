"""
Music playback cog for chewyBot.

Uses yt-dlp for audio streaming into Discord voice channels.
Slash commands: /play, /playlist, /skip, /stop, /pause, /resume,
                /queue, /nowplaying, /volume, /seek, /shuffle, /loop,
                /remove, /clearqueue

Full implementation: Phase 2.
Requirement: MUS-01 through MUS-04
"""
from __future__ import annotations

import discord
from discord.ext import commands


class MusicCog(commands.Cog, name="Music"):
    """Music playback cog — yt-dlp streaming. Full implementation in Phase 2."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        pass


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(MusicCog(bot))
