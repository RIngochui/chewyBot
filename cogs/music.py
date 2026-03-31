"""
Music playback cog for chewyBot.

Uses yt-dlp for audio streaming into Discord voice channels via FFmpegPCMAudio.
No temp files are written — all audio is streamed directly from yt-dlp URLs.

Slash commands: /play, /playlist, /skip, /stop, /pause, /resume,
                /queue, /nowplaying, /volume, /seek, /shuffle, /loop,
                /remove, /clearqueue

Requirements: MUS-01 through MUS-17
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import random
from typing import Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

from config import EMBED_COLOR, config

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Module-level constants                                                        #
# --------------------------------------------------------------------------- #

FFMPEG_OPTIONS: dict = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

YDL_OPTS: dict = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

YDL_PLAYLIST_OPTS: dict = {
    **YDL_OPTS,
    "noplaylist": False,
    "extract_flat": "in_playlist",
}

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #


def _format_duration(seconds: int) -> str:
    """Return duration as 'MM:SS' string."""
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


async def _fetch_song(url: str) -> Optional[dict]:
    """Fetch metadata and streaming URL for a single track using yt-dlp.

    Runs in a thread pool executor to avoid blocking the event loop.
    Returns a song dict or None on error.
    """
    loop = asyncio.get_event_loop()

    def _extract() -> Optional[dict]:
        try:
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return None
                # If result contains entries (playlist returned), take first
                if "entries" in info:
                    entries = [e for e in info["entries"] if e is not None]
                    if not entries:
                        return None
                    info = entries[0]
                return {
                    "url": info.get("url", ""),
                    "webpage_url": info.get("webpage_url", info.get("url", "")),
                    "title": info.get("title", "Unknown"),
                    "duration": int(info.get("duration", 0) or 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "requester_id": 0,
                    "requester": "",
                }
        except Exception:
            logger.exception("yt-dlp extraction failed for URL: %s", url)
            return None

    return await loop.run_in_executor(None, _extract)


async def _fetch_playlist(url: str) -> list[dict]:
    """Fetch all tracks from a YouTube playlist using yt-dlp.

    Returns a list of song dicts (may be empty on error or empty playlist).
    Each entry uses 'extract_flat' so only metadata is fetched up front;
    the streaming URL will be resolved when the song is actually played.
    """
    loop = asyncio.get_event_loop()

    def _extract() -> list[dict]:
        try:
            with yt_dlp.YoutubeDL(YDL_PLAYLIST_OPTS) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    return []
                entries = info.get("entries", [])
                songs: list[dict] = []
                for entry in entries:
                    if entry is None:
                        continue
                    # For flat-extracted entries, webpage_url may be in 'url'
                    webpage_url = entry.get("webpage_url") or entry.get("url", "")
                    songs.append({
                        "url": webpage_url,          # resolved later when played
                        "webpage_url": webpage_url,
                        "title": entry.get("title", "Unknown"),
                        "duration": int(entry.get("duration", 0) or 0),
                        "thumbnail": entry.get("thumbnail", ""),
                        "requester_id": 0,
                        "requester": "",
                    })
                return songs
        except Exception:
            logger.exception("yt-dlp playlist extraction failed for URL: %s", url)
            return []

    return await loop.run_in_executor(None, _extract)


# --------------------------------------------------------------------------- #
# QueueView — paginated /queue display                                          #
# --------------------------------------------------------------------------- #


class QueueView(discord.ui.View):
    """Paginated view for the music queue, 10 songs per page with prev/next buttons."""

    def __init__(
        self,
        queue: list[dict],
        current_index: int,
        page_size: int = 10,
    ) -> None:
        super().__init__(timeout=60)
        self.queue = queue
        self.current_index = current_index
        self.page_size = page_size
        self.current_page: int = 0

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        total_pages = max(1, -(-len(self.queue) // self.page_size))
        start = self.current_page * self.page_size
        end = start + self.page_size
        lines: list[str] = []
        for i, song in enumerate(self.queue[start:end], start=start):
            marker = "▶" if i == self.current_index else f"{i + 1}."
            duration_str = _format_duration(song["duration"])
            webpage = song.get("webpage_url", "")
            title = song.get("title", "Unknown")
            if webpage:
                lines.append(f"{marker} [{title}]({webpage}) — {duration_str}")
            else:
                lines.append(f"{marker} {title} — {duration_str}")
        embed = discord.Embed(
            title="Music Queue",
            description="\n".join(lines) if lines else "Queue is empty.",
            color=EMBED_COLOR,
        )
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{total_pages} \u2022 {len(self.queue)} tracks total"
        )
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
        total_pages = max(1, -(-len(self.queue) // self.page_size))
        self.current_page = min(total_pages - 1, self.current_page + 1)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


# --------------------------------------------------------------------------- #
# MusicCog                                                                      #
# --------------------------------------------------------------------------- #


class MusicCog(commands.Cog, name="Music"):
    """Music playback cog — yt-dlp streaming with queue management.

    Provides 9 slash commands: /play, /playlist, /skip, /stop, /pause,
    /resume, /queue, /nowplaying, /volume — plus auto-leave on channel empty.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Per-guild playback state, keyed by guild_id
        self._guild_state: dict[int, dict] = {}

    async def cog_load(self) -> None:
        """Called when cog is loaded."""
        logger.info("MusicCog loaded")

    # ----------------------------------------------------------------------- #
    # State management                                                          #
    # ----------------------------------------------------------------------- #

    def _get_state(self, guild_id: int) -> dict:
        """Return (creating if absent) the per-guild playback state dict."""
        if guild_id not in self._guild_state:
            self._guild_state[guild_id] = {
                "queue": [],            # list of song dicts
                "current_index": 0,
                "is_playing": False,
                "volume": 0.5,
                "loop": "off",          # 'off' | 'song' | 'queue'
                "channel_id": None,     # text channel ID for replies
                "start_time": None,     # datetime.datetime.utcnow() when song began
            }
        return self._guild_state[guild_id]

    # ----------------------------------------------------------------------- #
    # Internal helpers                                                          #
    # ----------------------------------------------------------------------- #

    async def _ensure_voice(
        self, interaction: discord.Interaction
    ) -> Optional[discord.VoiceClient]:
        """Ensure the bot is connected to the user's voice channel.

        Returns the VoiceClient, or None if the user is not in a voice channel.
        Moves the bot to the user's channel if it's in a different one.
        """
        user_voice = interaction.user.voice  # type: ignore[union-attr]
        if user_voice is None or user_voice.channel is None:
            embed = discord.Embed(
                description="You must be in a voice channel.",
                color=EMBED_COLOR,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return None

        channel = user_voice.channel
        guild = interaction.guild
        if guild is None:
            return None

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return vc

    async def _resolve_stream_url(self, song: dict) -> Optional[str]:
        """For flat-extracted playlist entries, resolve the actual streaming URL."""
        webpage_url = song.get("webpage_url", "")
        if not webpage_url:
            return None
        resolved = await _fetch_song(webpage_url)
        if resolved is None:
            return None
        return resolved.get("url")

    async def _play_next(self, guild: discord.Guild) -> None:
        """Core playback loop — plays the next song in the queue."""
        state = self._get_state(guild.id)
        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]

        if vc is None or not vc.is_connected():
            state["is_playing"] = False
            return

        if state["current_index"] >= len(state["queue"]):
            # Queue exhausted
            state["is_playing"] = False
            await self._log_embed(guild, "queue_end")
            return

        song = state["queue"][state["current_index"]]

        # If this was a flat-extracted playlist entry, the 'url' field is the
        # webpage URL and needs resolving to a real stream URL before playback.
        stream_url = song.get("url", "")
        if stream_url and ("youtube.com" in stream_url or "youtu.be" in stream_url):
            # Looks like a page URL, not a stream URL — resolve it
            resolved_url = await self._resolve_stream_url(song)
            if resolved_url:
                song["url"] = resolved_url
            else:
                logger.warning("Could not resolve stream URL for '%s', skipping.", song.get("title"))
                state["current_index"] += 1
                await self._play_next(guild)
                return

        # Check for seek_offset — set by /seek to restart current song at offset
        offset = state.pop("seek_offset", None)
        if offset is not None:
            before_opts = (
                f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -ss {offset}"
            )
        else:
            before_opts = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"

        try:
            source: discord.AudioSource = discord.FFmpegPCMAudio(
                song["url"], before_options=before_opts, options="-vn"
            )
            source = discord.PCMVolumeTransformer(source, volume=state["volume"])
        except Exception:
            logger.exception("Failed to create audio source for '%s'", song.get("title"))
            state["current_index"] += 1
            await self._play_next(guild)
            return

        # Adjust start_time to reflect seek position so /nowplaying progress is accurate
        if offset is not None:
            state["start_time"] = (
                datetime.datetime.utcnow() - datetime.timedelta(seconds=offset)
            )
        else:
            state["start_time"] = datetime.datetime.utcnow()
        state["is_playing"] = True

        def after_play(error: Optional[Exception]) -> None:
            if error:
                logger.error("Playback error in guild %d: %s", guild.id, error)
            # If seek_offset is set, a /seek command interrupted playback — do NOT advance index
            if state.get("seek_offset") is not None:
                # seek_offset will be consumed by the next _play_next call
                asyncio.run_coroutine_threadsafe(
                    self._play_next(guild), self.bot.loop
                )
                return
            # Advance index based on loop mode
            if state["loop"] == "song":
                pass  # keep same index
            elif (
                state["loop"] == "queue"
                and state["current_index"] + 1 >= len(state["queue"])
            ):
                state["current_index"] = 0
            else:
                state["current_index"] += 1
            asyncio.run_coroutine_threadsafe(
                self._play_next(guild), self.bot.loop
            )

        vc.play(source, after=after_play)
        await self._log_embed(guild, "song_start", song)

    async def _log_embed(
        self,
        guild: discord.Guild,
        event_type: str,
        song: Optional[dict] = None,
    ) -> None:
        """Send an informational embed to LOG_CHANNEL_ID."""
        try:
            channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
            if channel is None:
                return

            if event_type == "song_start" and song is not None:
                embed = discord.Embed(
                    title=f"Now Playing: {song['title']}",
                    url=song.get("webpage_url", ""),
                    color=EMBED_COLOR,
                )
                if song.get("thumbnail"):
                    embed.set_thumbnail(url=song["thumbnail"])
                embed.add_field(
                    name="Duration",
                    value=_format_duration(song["duration"]),
                    inline=True,
                )
                embed.add_field(
                    name="Requested By",
                    value=song.get("requester", "Unknown"),
                    inline=True,
                )

            elif event_type == "queue_end":
                embed = discord.Embed(
                    title="Queue Finished",
                    description="No more songs in queue.",
                    color=EMBED_COLOR,
                )

            elif event_type == "playlist_added" and song is not None:
                # 'song' here is actually {'name', 'count', 'thumbnail'}
                embed = discord.Embed(
                    title=f"Playlist Added: {song.get('name', 'Unknown')}",
                    color=EMBED_COLOR,
                )
                embed.add_field(
                    name="Tracks",
                    value=str(song.get("count", 0)),
                    inline=True,
                )
                if song.get("thumbnail"):
                    embed.set_thumbnail(url=song["thumbnail"])
            else:
                return

            await channel.send(embed=embed)  # type: ignore[union-attr]
        except Exception:
            logger.exception("Failed to send log embed for event '%s'", event_type)

    def _make_error_embed(self, description: str) -> discord.Embed:
        """Create a standard error embed."""
        return discord.Embed(description=description, color=EMBED_COLOR)

    # ----------------------------------------------------------------------- #
    # Slash commands                                                            #
    # ----------------------------------------------------------------------- #

    @app_commands.command(name="play", description="Play a YouTube video or search by query")
    @app_commands.describe(query="YouTube URL or search terms")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Play a track or add it to queue (MUS-01)."""
        await interaction.response.defer()

        vc = await self._ensure_voice(interaction)
        if vc is None:
            return

        song = await _fetch_song(query)
        if song is None:
            embed = self._make_error_embed("Could not find track. Please try a different query or URL.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        song["requester_id"] = interaction.user.id  # type: ignore[union-attr]
        song["requester"] = interaction.user.display_name  # type: ignore[union-attr]

        guild = interaction.guild
        if guild is None:
            return

        state = self._get_state(guild.id)
        state["channel_id"] = interaction.channel_id
        state["queue"].append(song)

        if state["is_playing"] or state["current_index"] < len(state["queue"]) - 1:
            # Music is already playing or there are other tracks ahead — queue it
            position = len(state["queue"]) - state["current_index"]
            embed = discord.Embed(
                title="Added to Queue",
                description=f"**[{song['title']}]({song.get('webpage_url', '')})**",
                color=EMBED_COLOR,
            )
            embed.add_field(name="Position in queue", value=str(position), inline=True)
            embed.add_field(name="Duration", value=_format_duration(song["duration"]), inline=True)
            await interaction.followup.send(embed=embed)
        else:
            # Nothing playing — start immediately
            await self._play_next(guild)
            embed = discord.Embed(
                title="Now Playing",
                description=f"**[{song['title']}]({song.get('webpage_url', '')})**",
                color=EMBED_COLOR,
            )
            embed.add_field(name="Duration", value=_format_duration(song["duration"]), inline=True)
            if song.get("thumbnail"):
                embed.set_thumbnail(url=song["thumbnail"])
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="playlist", description="Load a YouTube playlist into queue")
    @app_commands.describe(url="YouTube playlist URL")
    async def playlist(self, interaction: discord.Interaction, url: str) -> None:
        """Load a full playlist into the queue (MUS-02)."""
        await interaction.response.defer()

        vc = await self._ensure_voice(interaction)
        if vc is None:
            return

        songs = await _fetch_playlist(url)
        if not songs:
            embed = self._make_error_embed("No tracks found in playlist. Check the URL and try again.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            return

        state = self._get_state(guild.id)
        state["channel_id"] = interaction.channel_id

        requester_id = interaction.user.id  # type: ignore[union-attr]
        requester = interaction.user.display_name  # type: ignore[union-attr]

        # Try to get playlist title via yt-dlp (best effort)
        playlist_title = "YouTube Playlist"

        for s in songs:
            s["requester_id"] = requester_id
            s["requester"] = requester
            state["queue"].append(s)

        was_playing = state["is_playing"]
        if not was_playing:
            await self._play_next(guild)

        # Log embed
        first_thumb = songs[0].get("thumbnail", "") if songs else ""
        await self._log_embed(
            guild,
            "playlist_added",
            {"name": playlist_title, "count": len(songs), "thumbnail": first_thumb},
        )

        embed = discord.Embed(
            title="Playlist Added",
            description=f"Added **{len(songs)}** tracks to the queue from {playlist_title}",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip the current track (MUS-03)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is None or (not vc.is_playing() and not vc.is_paused()):
            embed = self._make_error_embed("Nothing is currently playing.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        vc.stop()  # Triggers after_play callback which advances current_index
        embed = discord.Embed(description="Skipped current track.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stop", description="Stop playback, clear queue, and disconnect")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop playback, clear queue, and disconnect (MUS-04)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is None:
            embed = self._make_error_embed("Bot is not connected to a voice channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        state = self._get_state(guild.id)
        vc.stop()
        state["queue"] = []
        state["current_index"] = 0
        state["is_playing"] = False
        await vc.disconnect()

        embed = discord.Embed(description="Stopped and disconnected.", color=EMBED_COLOR)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction) -> None:
        """Pause current playback (MUS-05)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is None:
            embed = self._make_error_embed("Bot is not connected to a voice channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if vc.is_playing():
            vc.pause()
            embed = discord.Embed(description="Paused.", color=EMBED_COLOR)
        else:
            embed = self._make_error_embed("Not playing.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="resume", description="Resume paused playback")
    async def resume(self, interaction: discord.Interaction) -> None:
        """Resume paused playback (MUS-06)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is None:
            embed = self._make_error_embed("Bot is not connected to a voice channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if vc.is_paused():
            vc.resume()
            embed = discord.Embed(description="Resumed.", color=EMBED_COLOR)
        else:
            embed = self._make_error_embed("Not paused.")
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------------------------- #
    # Task 2 commands: /queue, /nowplaying, /volume                            #
    # ----------------------------------------------------------------------- #

    @app_commands.command(name="queue", description="Show the current music queue")
    @app_commands.describe(page="Page number (default: 1)")
    async def queue_cmd(self, interaction: discord.Interaction, page: int = 1) -> None:
        """Display the current queue with pagination (MUS-07)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)
        queue = state["queue"]

        if not queue:
            embed = discord.Embed(
                title="Music Queue",
                description="Queue is empty.",
                color=EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed)
            return

        view = QueueView(queue, state["current_index"])
        # Jump to requested page (1-indexed from user, 0-indexed internally)
        page_size = view.page_size
        total_pages = max(1, -(-len(queue) // page_size))
        view.current_page = max(0, min(total_pages - 1, page - 1))

        await interaction.response.send_message(embed=view.build_embed(), view=view)

    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        """Show the current track with progress bar (MUS-08)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)

        if not state["is_playing"] or state["current_index"] >= len(state["queue"]):
            embed = self._make_error_embed("Nothing is currently playing.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        song = state["queue"][state["current_index"]]

        # Compute elapsed time and progress bar
        start_time: Optional[datetime.datetime] = state.get("start_time")
        if start_time is not None:
            elapsed = int((datetime.datetime.utcnow() - start_time).total_seconds())
        else:
            elapsed = 0
        elapsed = max(0, min(elapsed, song["duration"]))

        bar_length = 20
        filled = int(elapsed / max(song["duration"], 1) * bar_length)
        progress_bar = "\u2588" * filled + "\u2591" * (bar_length - filled)

        embed = discord.Embed(
            title=song["title"],
            url=song.get("webpage_url", ""),
            color=EMBED_COLOR,
        )
        if song.get("thumbnail"):
            embed.set_thumbnail(url=song["thumbnail"])
        embed.add_field(
            name="Duration",
            value=f"{_format_duration(elapsed)} / {_format_duration(song['duration'])}",
            inline=True,
        )
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        embed.add_field(
            name="Requested By",
            value=song.get("requester", "Unknown"),
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set playback volume (0\u2013100)")
    @app_commands.describe(level="Volume level 0\u2013100")
    async def volume(self, interaction: discord.Interaction, level: int) -> None:
        """Adjust playback volume live (MUS-09)."""
        if not 0 <= level <= 100:
            embed = self._make_error_embed("Volume must be between 0 and 100.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)
        state["volume"] = level / 100

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        if vc is not None and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = level / 100

        embed = discord.Embed(
            description=f"Volume set to **{level}%**",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------------------------- #
    # Task 3 commands: /seek, /shuffle, /loop                                  #
    # ----------------------------------------------------------------------- #

    @app_commands.command(name="seek", description="Seek to a position in the current track")
    @app_commands.describe(seconds="Position in seconds to seek to")
    async def seek(self, interaction: discord.Interaction, seconds: int) -> None:
        """Seek playback to the specified timestamp (MUS-10)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]
        state = self._get_state(guild.id)

        if vc is None or not state["is_playing"]:
            embed = self._make_error_embed("Nothing is playing.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if state["current_index"] >= len(state["queue"]):
            embed = self._make_error_embed("Nothing is playing.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        song = state["queue"][state["current_index"]]
        duration = song.get("duration", 0)

        if not (0 <= seconds <= duration):
            embed = self._make_error_embed("Position out of range.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Set seek_offset BEFORE calling vc.stop() so after_play sees it
        state["seek_offset"] = seconds
        vc.stop()  # Triggers after_play, which calls _play_next with seek_offset

        embed = discord.Embed(
            description=f"Seeked to {_format_duration(seconds)}",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="shuffle", description="Shuffle the music queue")
    async def shuffle(self, interaction: discord.Interaction) -> None:
        """Shuffle the queue, keeping current song at front (MUS-11)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)

        if len(state["queue"]) < 2:
            embed = self._make_error_embed("Queue has nothing to shuffle.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        current_song = (
            state["queue"][state["current_index"]] if state["is_playing"] else None
        )
        remaining = [
            s
            for i, s in enumerate(state["queue"])
            if i != state["current_index"] or not state["is_playing"]
        ]
        random.shuffle(remaining)
        if current_song is not None:
            state["queue"] = [current_song] + remaining
            state["current_index"] = 0
        else:
            state["queue"] = remaining
            state["current_index"] = 0

        embed = discord.Embed(
            description=f"Shuffled {len(state['queue'])} tracks.",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="loop", description="Set loop mode")
    @app_commands.describe(mode="Loop mode: off, song, or queue")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="off", value="off"),
            app_commands.Choice(name="song", value="song"),
            app_commands.Choice(name="queue", value="queue"),
        ]
    )
    async def loop(self, interaction: discord.Interaction, mode: str) -> None:
        """Set repeat mode: off, song, or queue (MUS-12)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)
        state["loop"] = mode

        embed = discord.Embed(
            description=f"Loop mode set to: **{mode}**",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------------------------- #
    # Task 4 commands: /remove, /clearqueue                                    #
    # ----------------------------------------------------------------------- #

    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    @app_commands.describe(position="1-based queue position to remove")
    async def remove(self, interaction: discord.Interaction, position: int) -> None:
        """Remove a track at the given 1-based position from the queue (MUS-13)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)

        if not (1 <= position <= len(state["queue"])):
            embed = self._make_error_embed("Invalid position.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        idx = position - 1  # convert 1-based to 0-based

        if idx == state["current_index"] and state["is_playing"]:
            embed = self._make_error_embed(
                "Cannot remove the currently playing track. Use /skip instead."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        removed = state["queue"].pop(idx)
        # Shift current_index down if the removed item was before the current song
        if idx < state["current_index"]:
            state["current_index"] -= 1

        embed = discord.Embed(
            description=f"Removed: **{removed['title']}**",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearqueue", description="Clear all songs from the queue")
    async def clearqueue(self, interaction: discord.Interaction) -> None:
        """Clear the queue, preserving the currently-playing track (MUS-14)."""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=self._make_error_embed("This command must be used in a server."),
                ephemeral=True,
            )
            return

        state = self._get_state(guild.id)
        count = len(state["queue"])

        if state["is_playing"] and state["current_index"] < len(state["queue"]):
            # Preserve the currently playing song
            current = state["queue"][state["current_index"]]
            state["queue"] = [current]
            state["current_index"] = 0
        else:
            state["queue"] = []
            state["current_index"] = 0

        embed = discord.Embed(
            description=f"Cleared {count} songs from queue.",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------------------------- #
    # Event handlers                                                            #
    # ----------------------------------------------------------------------- #

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-leave when voice channel has no non-bot members (MUS-15)."""
        # Ignore if it's the bot itself changing state
        if member.id == self.bot.user.id:  # type: ignore[union-attr]
            return

        # Only care about members leaving a channel
        if before.channel is None:
            return

        guild = member.guild
        vc: Optional[discord.VoiceClient] = guild.voice_client  # type: ignore[assignment]

        # Only act if the bot is in the channel the member left
        if vc is None or vc.channel != before.channel:
            return

        non_bot_members = [m for m in vc.channel.members if not m.bot]
        if len(non_bot_members) == 0:
            logger.warning(
                "Auto-left '%s' in guild %d — channel empty",
                before.channel.name,
                guild.id,
            )
            state = self._get_state(guild.id)
            state["queue"] = []
            state["current_index"] = 0
            state["is_playing"] = False
            await vc.disconnect()


# --------------------------------------------------------------------------- #
# Cog setup                                                                     #
# --------------------------------------------------------------------------- #


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook."""
    await bot.add_cog(MusicCog(bot))
