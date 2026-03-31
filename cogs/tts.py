"""
Text-to-speech cog for chewyBot.

Uses gTTS to generate audio to a temp file, plays in voice channel, deletes after.
Slash commands: /tts, /tts_lang, /tts_stop
Respects TTS_INTERRUPTS_MUSIC and TTS_MAX_CHARS env settings.

Full implementation: Phase 2.
Requirement: TTS-01 through TTS-04
"""
from __future__ import annotations

import discord
from discord.ext import commands


class TTSCog(commands.Cog, name="TTS"):
    """Text-to-speech cog — gTTS audio generation. Full implementation in Phase 2."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        pass


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(TTSCog(bot))
