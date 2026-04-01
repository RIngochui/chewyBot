"""
chewyBot entry point.

Boots the Discord bot: initializes the database, sets up logging, loads all 5
cogs with error isolation (one failure never stops others), registers slash
commands guild-specifically for instant sync, and connects to Discord with
exponential backoff retry (max 3 attempts).

Usage:
    python bot.py
"""
from __future__ import annotations

import asyncio
import logging
import sys

import discord
from discord.ext import commands

from config import config
from utils.logger import setup_logging
from database.db import init_db

logger = logging.getLogger(__name__)

# Explicit list of all cog module paths.
# Loading is attempted independently — one failure never prevents others (BOT-01).
COGS: list[str] = [
    "cogs.music",
    "cogs.tts",
    "cogs.emoji",
    "cogs.arb",
    "cogs.parlay",
]


class ChewyBot(commands.Bot):
    """The main Discord bot client for chewyBot."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.voice_states = True
        super().__init__(
            command_prefix="!",  # Fallback; slash commands are primary
            intents=intents,
        )

    async def setup_hook(self) -> None:
        """Called before the bot connects to Discord.

        Initializes the database, loads all cog extensions with error isolation,
        and registers slash commands to the configured guild for instant sync.
        """
        # Initialize database (WAL + tables + bot_config seed)
        await init_db(
            bankroll=config.BANKROLL,
            min_arb_pct=config.MIN_ARB_PCT,
            min_ev_pct=config.MIN_EV_PCT,
            enabled_sports=config.ENABLED_SPORTS,
        )

        # Load all cogs independently — one failure never stops others (BOT-01)
        failed_cogs: list[str] = []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info("Loaded cog: %s", cog)
            except Exception as exc:
                logger.error(
                    "Failed to load cog %s: %s", cog, exc, exc_info=True
                )
                failed_cogs.append(cog)

        if failed_cogs:
            logger.warning(
                "Skipped %d cog(s): %s", len(failed_cogs), ", ".join(failed_cogs)
            )

        # Register slash commands to specific guild for instant sync (not global 1-hour delay)
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=discord.Object(id=config.GUILD_ID))
        logger.info("Slash commands synced to guild %d", config.GUILD_ID)

    async def on_ready(self) -> None:
        """Called when the bot has connected to Discord and is ready.

        Sets the bot's custom status and posts a ready message to the log channel.
        """
        # Set bot status (BOT-03)
        await self.change_presence(
            activity=discord.CustomActivity(name="chewyBot is online!")
        )
        logger.info(
            "Logged in as %s (ID: %s)",
            self.user,
            self.user.id if self.user else "?",
        )

        # Post ready message to log channel (BOT-03)
        log_channel = self.get_channel(config.LOG_CHANNEL_ID)
        if log_channel and isinstance(log_channel, discord.TextChannel):
            await log_channel.send("chewyBot has logged in!")
        else:
            logger.warning(
                "LOG_CHANNEL_ID %d not found or not a text channel",
                config.LOG_CHANNEL_ID,
            )


async def main() -> None:
    """Create and start the bot with exponential backoff retry on connection failure.

    Retries up to 3 times (BOT-07) with 2s, 4s, 8s wait between attempts.
    Exits with code 1 after max retries or on unexpected errors.
    """
    bot = ChewyBot()

    # Setup logging after bot instance exists (Discord handler needs bot reference)
    setup_logging(bot, config.LOG_CHANNEL_ID)

    # Connect with exponential backoff retry (BOT-07: max 3 retries)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            await bot.start(config.DISCORD_TOKEN)
            break
        except discord.LoginFailure as exc:
            logger.error(
                "Discord login failed (attempt %d/%d): %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                logger.error("Max retries reached — exiting")
                sys.exit(1)
            wait = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
            logger.info("Retrying in %ds...", wait)
            await asyncio.sleep(wait)
        except Exception as exc:
            logger.error("Unexpected error starting bot: %s", exc, exc_info=True)
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
