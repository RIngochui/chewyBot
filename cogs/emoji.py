"""
Nitro-free emoji proxy cog for chewyBot.

Allows posting custom emoji as clean "[Username]: <emoji>" messages without Nitro.
Slash commands: /emote, /add_emote, /remove_emote, /list_emotes
Requires Manage Emojis permission for add/remove; validates <256KB, PNG/JPG/GIF.

Full implementation: Phase 2.
Requirement: EMO-01 through EMO-04
"""
from __future__ import annotations

import discord
from discord.ext import commands


class EmojiCog(commands.Cog, name="Emoji"):
    """Emoji proxy cog — Nitro-free emoji posting. Full implementation in Phase 2."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        pass


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(EmojiCog(bot))
