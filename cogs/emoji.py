"""
Nitro-free emoji proxy cog for chewyBot.

Allows posting custom emoji as clean "[Username]: <emoji>" messages without Nitro.
Slash commands: /emote, /add_emote, /remove_emote, /list_emotes

Permission rules:
  - /emote, /list_emotes: any user
  - /add_emote, /remove_emote: Manage Emojis permission required

Image validation for /add_emote:
  - Format: PNG, JPG, or GIF only (checked via Content-Type header)
  - Size: <256KB (262144 bytes)

Requirements: EMO-01 through EMO-05
"""
from __future__ import annotations

import logging
from difflib import get_close_matches

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from config import EMBED_COLOR

logger = logging.getLogger(__name__)


class EmojiBrowserView(discord.ui.View):
    """Paginated view for /list_emotes — 10 emoji per page, prev/next buttons."""

    PAGE_SIZE: int = 10

    def __init__(self, emojis: list[discord.Emoji]) -> None:
        super().__init__(timeout=60)
        self.emojis = emojis
        self.current_page = 0

    @property
    def total_pages(self) -> int:
        return max(1, -(-len(self.emojis) // self.PAGE_SIZE))

    def build_embed(self) -> discord.Embed:
        start = self.current_page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        page_emojis = self.emojis[start:end]
        embed = discord.Embed(
            title=f"Server Emojis ({len(self.emojis)} total)",
            color=EMBED_COLOR,
        )
        if page_emojis:
            # Show emoji mentions in a space-separated line
            embed.description = "  ".join(
                f"{e.mention} `:{e.name}:`" for e in page_emojis
            )
        else:
            embed.description = "No emojis on this page."
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages}")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.current_page = max(0, self.current_page - 1)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True


class EmojiCog(commands.Cog, name="Emoji"):
    """Nitro-free emoji proxy cog."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        logger.info("EmojiCog loaded")

    # ------------------------------------------------------------------
    # /emote [name] — EMO-01, EMO-05
    # ------------------------------------------------------------------

    @app_commands.command(name="emote", description="Post a server emoji as a message")
    @app_commands.describe(name="Emoji name to post")
    async def emote(self, interaction: discord.Interaction, name: str) -> None:
        """Reposts a server emoji as '[Username]: <emoji>' and deletes the slash invocation."""
        emoji_map = {e.name: e for e in interaction.guild.emojis}  # type: ignore[union-attr]

        if name in emoji_map:
            emoji = emoji_map[name]
        else:
            # EMO-05: suggest close matches
            matches = get_close_matches(name, list(emoji_map.keys()), n=3, cutoff=0.6)
            if not matches:
                embed = discord.Embed(
                    title="Emoji Not Found",
                    description=f"No emoji named `{name}` found and no close matches.",
                    color=EMBED_COLOR,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            suggestions = ", ".join(f"`:{m}:`" for m in matches)
            embed = discord.Embed(
                title="Emoji Not Found",
                description=f"Did you mean: {suggestions}?",
                color=EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Repost as clean message, then delete slash invocation (locked decision)
        display_name = interaction.user.display_name
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(f"[{display_name}]: {emoji}")  # type: ignore[union-attr]
        await interaction.delete_original_response()

    # ------------------------------------------------------------------
    # /list_emotes — EMO-04
    # ------------------------------------------------------------------

    @app_commands.command(name="list_emotes", description="Browse all server emojis")
    async def list_emotes(self, interaction: discord.Interaction) -> None:
        """Shows all server emojis in a paginated embed with prev/next navigation."""
        emojis = list(interaction.guild.emojis)  # type: ignore[union-attr]
        emojis.sort(key=lambda e: e.name.lower())

        if not emojis:
            embed = discord.Embed(
                title="No Server Emojis",
                description="This server has no custom emojis.",
                color=EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed)
            return

        view = EmojiBrowserView(emojis)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    # ------------------------------------------------------------------
    # /add_emote [name] [image_url] — EMO-02
    # ------------------------------------------------------------------

    @app_commands.command(name="add_emote", description="Add a custom emoji from an image URL")
    @app_commands.describe(
        name="Name for the emoji (letters, numbers, underscores only)",
        image_url="URL of the image (PNG, JPG, or GIF, max 256KB)",
    )
    async def add_emote(
        self,
        interaction: discord.Interaction,
        name: str,
        image_url: str,
    ) -> None:
        """Downloads an image and uploads it as a new custom server emoji."""
        # Permission check (EMO-02)
        if not interaction.user.guild_permissions.manage_emojis:  # type: ignore[union-attr]
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the **Manage Emojis** permission to add emojis.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Defer — download takes time
        await interaction.response.defer()

        # Name conflict check (EMO-05)
        existing_names = {e.name for e in interaction.guild.emojis}  # type: ignore[union-attr]
        if name in existing_names:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Name Conflict",
                    description=f"An emoji named `:{name}:` already exists.",
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        # Image download
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
        except (httpx.HTTPError, httpx.RequestError) as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Download Failed",
                    description=str(exc),
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        # Format validation — check Content-Type header (EMO-02)
        content_type = response.headers.get("content-type", "").lower()
        allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/avif"}
        # Strip parameters like "; charset=utf-8"
        mime = content_type.split(";")[0].strip()
        if mime not in allowed_types:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Invalid Format",
                    description="Image must be PNG, JPG, GIF, or AVIF.",
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        # Size validation (<256KB = 262144 bytes) (EMO-02)
        image_bytes = response.content
        if len(image_bytes) > 262_144:
            kb = len(image_bytes) // 1024
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Image Too Large",
                    description=f"Image is {kb}KB. Maximum allowed is 256KB.",
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        # Upload to Discord (EMO-02)
        try:
            emoji = await interaction.guild.create_custom_emoji(  # type: ignore[union-attr]
                name=name,
                image=image_bytes,
                reason=f"Added by {interaction.user.display_name} via /add_emote",
            )
        except discord.HTTPException as exc:
            logger.error("Failed to create emoji %s: %s", name, exc)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Upload Failed",
                    description=f"Discord rejected the emoji: {exc}",
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=discord.Embed(
                title="Emoji Added",
                description=f"Added <:{emoji.name}:{emoji.id}> as `:{emoji.name}:`",
                color=EMBED_COLOR,
            )
        )

    # ------------------------------------------------------------------
    # /remove_emote [name] — EMO-03
    # ------------------------------------------------------------------

    @app_commands.command(name="remove_emote", description="Remove a custom emoji from the server")
    @app_commands.describe(name="Name of the emoji to remove")
    async def remove_emote(
        self,
        interaction: discord.Interaction,
        name: str,
    ) -> None:
        """Removes a named custom emoji from the server."""
        # Permission check (EMO-03)
        if not interaction.user.guild_permissions.manage_emojis:  # type: ignore[union-attr]
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the **Manage Emojis** permission to remove emojis.",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        emoji_map = {e.name: e for e in interaction.guild.emojis}  # type: ignore[union-attr]

        if name not in emoji_map:
            # EMO-05: suggest close matches
            matches = get_close_matches(name, list(emoji_map.keys()), n=3, cutoff=0.6)
            msg = f"No emoji named `:{name}:` found."
            if matches:
                suggestions = ", ".join(f"`:{m}:`" for m in matches)
                msg += f" Did you mean: {suggestions}?"
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Emoji Not Found",
                    description=msg,
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        emoji = emoji_map[name]
        try:
            await emoji.delete(
                reason=f"Removed by {interaction.user.display_name} via /remove_emote"
            )
        except discord.HTTPException as exc:
            logger.error("Failed to delete emoji %s: %s", name, exc)
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Delete Failed",
                    description=str(exc),
                    color=EMBED_COLOR,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Emoji Removed",
                description=f"Removed `:{name}:`",
                color=EMBED_COLOR,
            )
        )


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(EmojiCog(bot))
