"""
Text-to-speech cog for chewyBot.

Uses gTTS to generate audio to a temp file, plays in voice channel, deletes after.
Slash commands: /tts, /tts_lang, /tts_stop
Respects TTS_INTERRUPTS_MUSIC and TTS_MAX_CHARS env settings.
FIFO queue for multiple TTS requests.

Requirements: TTS-01 through TTS-07
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from gtts import gTTS
from gtts.lang import tts_langs

from config import EMBED_COLOR, config
from database.db import get_db
from database.queries import GET_TTS_LANG, UPSERT_TTS_LANG

logger = logging.getLogger(__name__)


def _generate_tts_file(text: str, lang: str) -> str:
    """Generate a gTTS MP3 to a temp file. Returns the temp file path.

    Runs in a thread executor to avoid blocking the event loop.
    Caller is responsible for deleting the file via try/finally.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp.close()
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(tmp.name)
    return tmp.name


class TTSCog(commands.Cog, name="TTS"):
    """Text-to-speech cog — gTTS audio generation with FIFO queue and language persistence."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tts_queue: asyncio.Queue[tuple[str, str, discord.Guild, int]] = asyncio.Queue()
        # Queue items: (text, lang, guild, requester_id)
        self._is_tts_active: bool = False

    async def cog_load(self) -> None:
        logger.info("TTSCog loaded")

    async def _get_user_lang(self, user_id: int) -> str:
        """Retrieve user's preferred TTS language from bot_config, default 'en'."""
        key = f"tts_lang_{user_id}"
        async with get_db() as db:
            cursor = await db.execute(GET_TTS_LANG, (key,))
            row = await cursor.fetchone()
        return row["value"] if row else "en"

    async def _play_tts(self, text: str, lang: str, guild: discord.Guild) -> None:
        """Generate TTS audio, play in voice channel, then delete temp file."""
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            logger.warning("TTS: bot not in voice channel for guild %d", guild.id)
            return
        loop = asyncio.get_event_loop()
        tmp_path: str | None = None
        try:
            tmp_path = await loop.run_in_executor(None, _generate_tts_file, text, lang)
            done_event = asyncio.Event()

            def after_tts(error: Exception | None) -> None:
                if error:
                    logger.error("TTS playback error: %s", error)
                loop.call_soon_threadsafe(done_event.set)

            source = discord.FFmpegPCMAudio(tmp_path)
            vc.play(source, after=after_tts)
            await done_event.wait()
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _process_tts_queue(self, guild: discord.Guild) -> None:
        """Drain the TTS FIFO queue sequentially."""
        if self._is_tts_active:
            return
        self._is_tts_active = True
        try:
            while not self._tts_queue.empty():
                text, lang, q_guild, _ = await self._tts_queue.get()
                if q_guild.id == guild.id:
                    await self._play_tts(text, lang, guild)
                self._tts_queue.task_done()
        finally:
            self._is_tts_active = False

    @app_commands.command(name="tts", description="Convert text to speech in your voice channel")
    @app_commands.describe(text="Text to speak (max TTS_MAX_CHARS characters)")
    async def tts(self, interaction: discord.Interaction, text: str) -> None:
        """Play TTS audio in the user's current voice channel. Queues if TTS is active."""
        # TTS-07: Error if user is not in a voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel to use TTS.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # TTS-06: Enforce TTS_MAX_CHARS limit before generation
        if len(text) > config.TTS_MAX_CHARS:
            embed = discord.Embed(
                description=f"Message too long. Maximum {config.TTS_MAX_CHARS} characters.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        lang = await self._get_user_lang(interaction.user.id)

        # Ensure bot is in the user's voice channel
        vc = interaction.guild.voice_client
        if vc is None or not vc.is_connected():
            await interaction.user.voice.channel.connect()

        # TTS-05: TTS_INTERRUPTS_MUSIC behavior
        if config.TTS_INTERRUPTS_MUSIC:
            # Interrupt: stop current playback and play TTS immediately
            vc = interaction.guild.voice_client
            if vc and vc.is_playing():
                vc.stop()
            await self._play_tts(text, lang, interaction.guild)
            await interaction.followup.send("TTS played.", ephemeral=True)
        else:
            # Queue behavior (default): FIFO queue
            await self._tts_queue.put((text, lang, interaction.guild, interaction.user.id))
            asyncio.create_task(self._process_tts_queue(interaction.guild))
            if self._is_tts_active:
                await interaction.followup.send("TTS queued.", ephemeral=True)
            else:
                await interaction.followup.send("TTS playing.", ephemeral=True)

    @app_commands.command(name="tts_lang", description="Set your preferred TTS language")
    @app_commands.describe(language_code="ISO 639-1 language code (e.g. en, es, fr, ja)")
    async def tts_lang(self, interaction: discord.Interaction, language_code: str) -> None:
        """Persist the user's preferred TTS language in bot_config."""
        lang = language_code.lower().strip()
        # TTS-02: Validate against gTTS supported language codes
        supported = tts_langs()
        if lang not in supported:
            embed = discord.Embed(
                description=f"Invalid language code '{lang}'. Examples: en, es, fr, de, ja, ko, zh",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        key = f"tts_lang_{interaction.user.id}"
        async with get_db() as db:
            await db.execute(UPSERT_TTS_LANG, (key, lang))

        embed = discord.Embed(
            description=f"TTS language set to: **{supported[lang]}** (`{lang}`)",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tts_stop", description="Stop current TTS playback")
    async def tts_stop(self, interaction: discord.Interaction) -> None:
        """Stop TTS playback and clear the TTS queue."""
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            embed = discord.Embed(
                description="TTS stopped.",
                color=EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Nothing is currently playing.", ephemeral=True
            )
        # TTS-03: Clear the TTS queue
        self._tts_queue = asyncio.Queue()


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(TTSCog(bot))
