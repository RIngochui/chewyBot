"""
chewyBot logging infrastructure.

Provides setup_logging() which attaches two handlers to the root logger:

  1. RotatingFileHandler  — INFO+, 5 MB max, 5 backups, writes to chewybot.log
  2. DiscordHandler        — WARNING+, async task-based, writes to LOG_CHANNEL_ID

DiscordHandler drops messages silently if the bot is not yet ready — it never
blocks the event loop.  All scheduling uses asyncio.create_task() so the
Discord send happens asynchronously after the caller returns.
"""

import asyncio
import logging
import logging.handlers
from pathlib import Path

import discord

# Exact format agreed in locked decisions (01-CONTEXT.md)
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Log file at project root (same directory as bot.py / db)
LOG_FILE: Path = Path("chewybot.log")


class DiscordHandler(logging.Handler):
    """A non-blocking logging handler that posts WARNING+ records to a Discord channel.

    Messages are scheduled as asyncio tasks so they never block the event loop.
    If the bot is not yet ready (e.g., early-startup errors), the record is
    dropped gracefully — it will already be captured by the file handler.
    """

    def __init__(
        self,
        bot: discord.Client,
        channel_id: int,
        level: int = logging.WARNING,
    ) -> None:
        super().__init__(level)
        self.bot: discord.Client = bot
        self.channel_id: int = channel_id

    def emit(self, record: logging.LogRecord) -> None:
        """Format the log record and schedule a Discord send as an asyncio task."""
        # Drop immediately if the bot hasn't connected — never blocks
        if not self.bot.is_ready():
            return

        try:
            msg = self.format(record)
            # Truncate to 1990 chars to stay within Discord's 2000-char limit
            if len(msg) > 1990:
                msg = msg[:1990]
            formatted = f"```\n{msg}\n```"
            asyncio.create_task(self._send_to_discord(formatted))
        except Exception:
            self.handleError(record)

    async def _send_to_discord(self, msg: str) -> None:
        """Send a pre-formatted message to the configured Discord channel.

        Fails silently — a Discord send failure must never break the logging chain.
        """
        try:
            channel = self.bot.get_channel(self.channel_id)
            if channel is not None:
                await channel.send(msg)  # type: ignore[union-attr]
        except Exception:
            pass  # Silent: Discord logging failure must not propagate


def setup_logging(bot: discord.Client, log_channel_id: int) -> None:
    """Configure the root logger with a rotating file handler and a Discord handler.

    Call this once, before any cog is loaded, from bot.py's setup_hook or on_ready.

    Args:
        bot:            The discord.Client (or discord.ext.commands.Bot) instance.
        log_channel_id: Discord channel ID to which WARNING+ records are posted.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # --- Rotating file handler (INFO+) -----------------------------------
    file_handler = logging.handlers.RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)

    # --- Discord channel handler (WARNING+) ------------------------------
    discord_handler = DiscordHandler(bot=bot, channel_id=log_channel_id)
    discord_handler.setLevel(logging.WARNING)

    # Shared formatter for both handlers
    formatter = logging.Formatter(LOG_FORMAT)
    file_handler.setFormatter(formatter)
    discord_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(discord_handler)

    # Suppress discord.py internal noise (http, gateway, etc.)
    logging.getLogger("discord").setLevel(logging.WARNING)
