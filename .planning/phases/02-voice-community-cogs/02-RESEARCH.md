# Phase 2: Voice & Community Cogs - Research

**Researched:** 2026-03-31  
**Domain:** discord.py voice client integration, audio streaming (yt-dlp, gTTS), emoji management  
**Confidence:** HIGH

## Summary

Phase 2 implements three fully functional cogs on the Phase 1 foundation: MusicCog (yt-dlp streaming with 14 slash commands and queue management), TTSCog (gTTS audio with 3 slash commands), and EmojiCog (Nitro-free emoji proxy with 4 slash commands). All three cogs are built with the established patterns from Phase 1 (async logging, type hints, config.py integration, SQLite persistence, error handling). The primary technical challenges are voice client lifecycle management (auto-leave when channel empties), yt-dlp format selection for streaming URLs, and TTS language persistence. All are solved problems with well-documented patterns in the discord.py ecosystem.

**Primary recommendation:** Use discord.py 2.x VoiceClient with FFmpegPCMAudio directly (no third-party music libraries); queue management via simple list with index pointer; TTS queuing with FIFO; emoji proxy via discord.ui.View with pagination.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Queue data structure: `list` with `current_index` pointer — enables inspect, shuffle, remove-by-position, and /queue display without complexity of asyncio.Queue
- Unexpected voice disconnect: log error, clear queue state, send notification to channel — no auto-reconnect (avoids infinite loops)
- `/play` while music is playing: queue the new track, respond "Added to queue: X" — consistent with standard Discord bot behavior
- yt-dlp audio delivery: stream directly via `FFmpegPCMAudio` + yt-dlp extractors — no temp disk usage, standard discord.py pattern
- Multiple TTS requests while TTS is playing: FIFO queue — consistent with music queue, better UX than rejection
- `/tts_lang` persistence: per-user in `bot_config` table (key: `tts_lang_{user_id}`) — persists across restarts, reuses existing DB layer
- `TTS_INTERRUPTS_MUSIC=false` behavior: queue TTS after current song finishes, confirm with "TTS queued" message
- Temp file: `tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)` — OS-managed, cleanup via try/finally after playback
- `/list_emotes` pagination: `discord.ui.View` with prev/next buttons, 10 emoji per page — better UX, no page argument needed
- Fuzzy name matching: `difflib.get_close_matches(name, all_names, n=3, cutoff=0.6)` — suggests closest per spec EMO-05
- `/add_emote` image source: URL parameter only — matches spec `[image_url]`, simpler validation
- Slash invocation deletion: delete after successful repost — avoids empty chat gap if repost fails

### Claude's Discretion
- Exact yt-dlp format options (bestaudio/best, prefer_ffmpeg, etc.)
- Per-guild vs per-cog state management patterns
- Error embed color vs informational embed color conventions (inherit Phase 1 EMBED_COLOR)
- Specific queue-full behavior if queue grows extremely large

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MUS-01 | /play [query or URL] — searches YouTube or plays direct URL; bot joins user's voice channel | yt-dlp YoutubeDL.extract_info() + ytsearch prefix; discord.py VoiceClient.connect() |
| MUS-02 | /playlist [url] — loads a YouTube playlist into queue | yt-dlp playlist extraction; queue append pattern |
| MUS-03 | /skip — skips current song | VoiceClient.stop() triggers after callback; queue advance |
| MUS-04 | /stop — stops playback, clears queue, bot leaves voice channel | VoiceClient.disconnect(); queue clear |
| MUS-05 | /pause — pauses playback | VoiceClient.pause() method |
| MUS-06 | /resume — resumes playback | VoiceClient.resume() method |
| MUS-07 | /queue — shows current queue as paginated embed (10 songs per page) | discord.ui.View pagination; queue slice |
| MUS-08 | /nowplaying — shows current song with title, thumbnail, duration, and text progress bar | yt-dlp metadata (title, duration, thumbnail); current_time tracking |
| MUS-09 | /volume [0-100] — sets playback volume | PCMVolumeTransformer.volume property |
| MUS-10 | /seek [seconds] — seeks to timestamp in current track | VoiceClient.stop() + resume at offset; yt-dlp redirect URL support |
| MUS-11 | /shuffle — shuffles the queue | list.shuffle(); current_index reset to 0 |
| MUS-12 | /loop [off/song/queue] — sets repeat mode | Loop state variable; queue logic on song end |
| MUS-13 | /remove [position] — removes song at queue position | list.pop(position) |
| MUS-14 | /clearqueue — clears entire queue | queue = [] reset |
| MUS-15 | Bot auto-leaves when voice channel is empty | on_voice_state_update event; vc.channel.members count check |
| MUS-16 | Embeds posted to LOG_CHANNEL_ID on: song start, playlist added, queue end | Existing logger.py; embed builder from Phase 1 |
| MUS-17 | Uses yt-dlp + discord.py voice client (no discord-music-player) | Direct VoiceClient.play(FFmpegPCMAudio(url)) |
| TTS-01 | /tts [text] — converts text to speech via gTTS, plays in user's current voice channel | gTTS.save() to temp file; VoiceClient.play() |
| TTS-02 | /tts_lang [language_code] — sets preferred TTS language (default: en) | GET/UPSERT bot_config; ISO 639-1 validation |
| TTS-03 | /tts_stop — stops current TTS playback | VoiceClient.stop() |
| TTS-04 | Audio generated to temp file, played, deleted after playback | tempfile.NamedTemporaryFile(delete=False); try/finally cleanup |
| TTS-05 | TTS_INTERRUPTS_MUSIC env var controls whether TTS queues after current song or interrupts | FIFO queue logic; conditional behavior in after callback |
| TTS-06 | TTS_MAX_CHARS env var enforces max character limit (default: 300) | Input validation before gTTS.save() |
| TTS-07 | Error returned if user is not in a voice channel | member.voice.channel check; embed error response |
| EMO-01 | /emote [name] — bot reposts as clean "[Username]: <emoji>" message; slash command invocation deleted | Guild.fetch_emoji(); interaction.message.delete(); channel.send() |
| EMO-02 | /add_emote [name] [image_url] — downloads image, validates <256KB and PNG/JPG/GIF format, uploads as custom server emoji; requires Manage Emojis permission | httpx.get() for download; aiofiles for size check; Guild.create_custom_emoji() |
| EMO-03 | /remove_emote [name] — removes custom emoji from server; requires Manage Emojis permission | Guild.fetch_emoji(); Emoji.delete(); permission check via interaction.permissions |
| EMO-04 | /list_emotes — paginated embed with emoji previews | Guild.emojis; discord.ui.View pagination; emoji formatting as `<:name:id>` |
| EMO-05 | Graceful name conflict errors; suggests closest match if emoji not found | difflib.get_close_matches() as locked decision |
</phase_requirements>

## Standard Stack

### Core Audio/Voice
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| discord.py | 2.7.1 | Voice client, slash commands, message handling | Official Discord Python library; active maintenance; discord.py 2.x native app_commands |
| yt-dlp | 2025.3.31 | YouTube audio extraction, metadata, streaming | Actively maintained fork of youtube-dl; supports direct streaming without temp files; excellent format selection |
| gTTS | 2.5.3 | Text-to-speech audio generation | Simple Google Translate TTS wrapper; 100+ language support; generates MP3 to file |
| ffmpeg | system | Audio encoding, stream multiplexing | Required by discord.py FFmpegPCMAudio; handles Opus encoding; installed via brew/apt |

### Supporting Libraries (Phase 1 Foundation)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiosqlite | 0.22.1 | Async SQLite for TTS language persistence | Per-user language config stored in bot_config table |
| httpx | 0.28.1 | Async HTTP client | /add_emote image download validation (size/format check) |
| pydantic | 2.11.3 | Data validation | Validating language codes (ISO 639-1), embed payloads |
| python-dotenv | 1.1.0 | .env loading via pydantic-settings | TTS_INTERRUPTS_MUSIC, TTS_MAX_CHARS config |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yt-dlp direct streaming | youtube_dl (original) | Slower updates, fewer format options; no streaming without temp files |
| yt-dlp direct streaming | discord-music-player library | Abstraction hides VoiceClient details; harder to debug voice issues; added maintenance burden |
| gTTS | pyttsx3 | Requires system TTS (espeak/SAPI5); no internet needed; lower quality voices |
| gTTS | Edge TTS | Microsoft service; requires different API; not mentioned in spec |
| discord.ui.View pagination | discord-py-pagination library | Third-party deps; less control; overkill for 4 emoji commands |

**Installation:**
```bash
pip install -r requirements.txt
brew install ffmpeg  # macOS
# or: apt-get install ffmpeg  # Linux
```

**Version verification (as of 2026-03-31):**
- discord.py 2.7.1 — Latest stable, released 2025-12
- yt-dlp 2025.3.31 — Rolling weekly releases, current version
- gTTS 2.5.3 — Latest stable, Python 3.9+
- aiosqlite 0.22.1 — Latest async sqlite, Python 3.8+
- ffmpeg 6.0+ (system-level, version varies by OS)

## Architecture Patterns

### Recommended Project Structure
```
cogs/
├── music.py          # MusicCog: 14 slash commands, queue, VoiceClient management
├── tts.py            # TTSCog: 3 slash commands, temp file audio, language persistence
├── emoji.py          # EmojiCog: 4 slash commands, discord.ui.View pagination
├── arb.py            # (Phase 3) Arbitrage scanner
└── parlay.py         # (Phase 4) NBA parlay AI

database/
├── db.py             # get_db() context manager (Phase 1, reused)
└── queries.py        # All SQL including bot_config UPSERT (Phase 1, reused)

utils/
├── logger.py         # setup_logging() (Phase 1, reused)
└── formatters.py     # embed builders (Phase 1 stub, implement as needed in Phase 2)

config.py            # Config object with TTS_INTERRUPTS_MUSIC, TTS_MAX_CHARS (Phase 1)
bot.py               # ChewyBot entry point with cog loader (Phase 1)
requirements.txt     # yt-dlp, gTTS, discord.py, aiosqlite, httpx pinned versions
```

### Pattern 1: Voice Client Queue Management (Music)
**What:** List with index pointer for queue position; current audio source wrapped with volume control.  
**When to use:** Music cog requires inspect, shuffle, remove-by-position, display operations.  
**Example:**
```python
# Source: discord.py VoiceClient.play(source, after=callback) pattern
from discord import FFmpegPCMAudio, PCMVolumeTransformer

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue: list[dict] = []  # [{url, title, duration, thumbnail, requester_id}, ...]
        self.current_index: int = 0
        self.is_playing: bool = False
    
    async def play_next(self, voice_client):
        """Play next song in queue or stop if queue exhausted."""
        if self.current_index >= len(self.queue):
            self.is_playing = False
            return
        
        song = self.queue[self.current_index]
        # yt-dlp provides direct streaming URL via extract_info(url, process=False)
        source = FFmpegPCMAudio(
            song['url'],
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        )
        source = PCMVolumeTransformer(source, volume=self.volume)
        
        def on_song_end(error):
            if error:
                logger.error("Playback error: %s", error)
            self.current_index += 1
            asyncio.create_task(self.play_next(voice_client))
        
        voice_client.play(source, after=on_song_end)
        self.is_playing = True
```

### Pattern 2: TTS FIFO Queue with Interruption Control
**What:** Separate queue for TTS requests; behavior depends on TTS_INTERRUPTS_MUSIC config.  
**When to use:** Multiple TTS requests arrive while music is playing or TTS is playing.  
**Example:**
```python
# Source: Config-driven queue behavior per CONTEXT.md locked decision
class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tts_queue: asyncio.Queue = asyncio.Queue()
        self.is_tts_playing = False
    
    async def handle_tts_request(self, interaction, text, user_id):
        """Queue TTS request or interrupt music based on config."""
        if config.TTS_INTERRUPTS_MUSIC and self.is_tts_playing:
            # Interrupt: stop current TTS and play immediately
            if interaction.guild.voice_client:
                interaction.guild.voice_client.stop()
        else:
            # Queue: add to FIFO queue
            await self.tts_queue.put((text, user_id, interaction))
        
        # Process queue asynchronously
        asyncio.create_task(self._process_tts_queue(interaction.guild))
    
    async def _process_tts_queue(self, guild):
        """Process TTS queue FIFO; prevents backlog starvation."""
        while not self.tts_queue.empty():
            text, user_id, interaction = await self.tts_queue.get()
            await self._play_tts(guild, text, user_id)
```

### Pattern 3: Emoji Proxy with discord.ui.View Pagination
**What:** Paginated embed with prev/next buttons; 10 emoji per page; fuzzy matching on name lookup.  
**When to use:** /list_emotes (large server emoji lists) and /emote (exact match with suggestions).  
**Example:**
```python
# Source: discord.py ui.View pattern per CONTEXT.md
import discord
from discord import ui
from difflib import get_close_matches

class EmojiBrowserView(ui.View):
    def __init__(self, emojis: list, page_size: int = 10):
        super().__init__(timeout=60)
        self.emojis = emojis
        self.page_size = page_size
        self.current_page = 0
    
    def get_page_embed(self):
        """Build embed for current page."""
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_emojis = self.emojis[start:end]
        
        embed = discord.Embed(title="Server Emojis", color=EMBED_COLOR)
        embed.description = " ".join(f"{e.mention}" for e in page_emojis)
        embed.set_footer(text=f"Page {self.current_page + 1} of {-(-len(self.emojis) // self.page_size)}")
        return embed
    
    @ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction, button):
        self.current_page = max(0, self.current_page - 1)
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)
    
    @ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction, button):
        max_page = -(-len(self.emojis) // self.page_size) - 1
        self.current_page = min(max_page, self.current_page + 1)
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

class EmojiCog(commands.Cog):
    @app_commands.command(name="list_emotes")
    async def list_emotes(self, interaction: discord.Interaction):
        """List all server emojis with pagination."""
        emojis = list(interaction.guild.emojis)
        if not emojis:
            embed = discord.Embed(title="No emojis found", color=EMBED_COLOR)
            return await interaction.response.send_message(embed=embed)
        
        view = EmojiBrowserView(emojis)
        embed = view.get_page_embed()
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="emote")
    async def emote_command(self, interaction: discord.Interaction, name: str):
        """Find and repost emoji."""
        emojis_dict = {e.name: e for e in interaction.guild.emojis}
        
        if name in emojis_dict:
            emoji = emojis_dict[name]
        else:
            # Fuzzy match if exact name not found (EMO-05)
            matches = get_close_matches(name, emojis_dict.keys(), n=3, cutoff=0.6)
            if not matches:
                embed = discord.Embed(title="Emoji not found", color=EMBED_COLOR)
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            emoji = emojis_dict[matches[0]]
            embed = discord.Embed(
                title="Did you mean?",
                description=f"Closest match: `{emoji.name}`",
                color=EMBED_COLOR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Repost emoji as clean message
        msg = await interaction.channel.send(f"[{interaction.user.display_name}]: {emoji}")
        
        # Delete slash command invocation (avoid empty chat gap)
        await interaction.response.defer()
        await interaction.delete_original_response()
```

### Pattern 4: Slash Commands with interaction.response and Type Hints
**What:** All voice/emoji commands use app_commands.command with interaction parameter; responses via interaction.response.
**When to use:** Every command in music, tts, emoji cogs.  
**Example:**
```python
# Source: discord.py app_commands pattern; Phase 1 established
from discord.ext import commands
from discord import app_commands

class MusicCog(commands.Cog):
    @app_commands.command(name="play", description="Play a song from YouTube or URL")
    @app_commands.describe(query="Song name or YouTube URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Play a track and join user's voice channel."""
        # Defer response if operation takes > 3s (yt-dlp extraction)
        await interaction.response.defer()
        
        # Type hints on all parameters; validation before processing
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(title="Error", description="You must be in a voice channel", color=EMBED_COLOR)
            return await interaction.followup.send(embed=embed)
        
        # Process and respond
        await interaction.followup.send(f"Added to queue: {query}")
```

### Anti-Patterns to Avoid
- **Hardcoded file paths in /add_emote:** Store Content-Length check via httpx HEAD request, not by guessing extension — prevents bypassing 256KB limit
- **Blocking yt-dlp extraction:** Always `await asyncio.create_task()` or `asyncio.gather()` — YoutubeDL.extract_info() is CPU-bound, never block event loop
- **Forgetting `before_options` on FFmpegPCMAudio:** YouTube URLs expire in 25-30 seconds without reconnect flags; always include `"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"`
- **Temp file race conditions:** Use `tempfile.NamedTemporaryFile(delete=False)` + explicit `os.unlink()` in finally block — don't rename to fixed names like "song.mp3"
- **Not checking member count before auto-leave:** Use `len(vc.channel.members)` not just `vc.channel.members` — bot is always in the list, check for exactly 1
- **Ignoring TTS_INTERRUPTS_MUSIC config:** Behavior varies; queue logic must check this flag, not hard-code interruption
- **Pagination with page number argument:** Use stateful View with current_page variable — cleaner UX than /queue 2

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YouTube search & metadata extraction | Custom regex parsing, XML crawling, or raw requests | yt-dlp YoutubeDL.extract_info() with ytsearch prefix | Handles rate limits, format selection, metadata extraction, supports playlists |
| Text-to-speech generation | Custom festival/espeak integration or API wrappers | gTTS cloud API | Free, 100+ languages, natural voices, no system TTS setup required |
| Voice client connection lifecycle | Manual state tracking (bot in channel, members count, reconnect logic) | discord.py VoiceClient methods + on_voice_state_update event | Built-in error handling, automatic reconnect, safe state machine |
| URL audio streaming without temp files | Download to disk then stream, or custom stream splitter | yt-dlp extract_info(url, process=False) + FFmpegPCMAudio(url) | yt-dlp provides streaming URLs with 25-30s TTL; FFmpeg handles HTTP reconnect |
| Pagination UI | Custom button handling, page state in message metadata | discord.ui.View class with button callbacks and instance variables | Timeout safety, state isolation, view cleanup on timeout |
| Emoji name fuzzy matching | Edit distance calculation or substring search | difflib.get_close_matches(cutoff=0.6, n=3) | Proven algorithm, configurable threshold, limits result set |
| SQLite async access | Manual threading.Thread wrapper or sync context | aiosqlite async context manager | Non-blocking I/O, proper cursor/connection cleanup, built-in transaction support |

**Key insight:** Voice client lifecycle (connect/disconnect/playback), audio format handling, and TTS generation are complex domains with hidden requirements (reconnect logic, Opus encoding, language code validation). Leveraging battle-tested libraries (discord.py, yt-dlp, gTTS) prevents weeks of debugging edge cases (expired YouTube URLs, missing system TTS, race conditions in temp file cleanup).

## Common Pitfalls

### Pitfall 1: YouTube URL Expiry and Reconnection Loss
**What goes wrong:** Bot starts playing a song, but after 25-30 seconds the URL expires and playback stops silently or with a cryptic FFmpeg error.  
**Why it happens:** YouTube redirects requests through temporary signed URLs that expire quickly; FFmpeg needs explicit reconnect options or it fails on the first dropped packet.  
**How to avoid:**
- Always use `before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"` when creating FFmpegPCMAudio
- Test with long songs (5+ min) to catch expiry mid-playback
- Log FFmpeg stderr to detect connection errors early: `FFmpegPCMAudio(url, stderr=asyncio.subprocess.PIPE)`
**Warning signs:** "Connection refused", "HTTP 403", silent playback stop after 25s

### Pitfall 2: Temp File Cleanup Race Condition
**What goes wrong:** Multiple TTS requests create temp files with the same name (e.g., "tts.mp3"); one request deletes the file while another is still playing, causing playback corruption or "file not found" errors.  
**Why it happens:** gTTS.save() defaults to a fixed filename if you pass only a directory; deleting too early causes race conditions.  
**How to avoid:**
- Use `tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir=None)` to get unique OS-managed names
- Always wrap playback in try/finally: `try: await play(); finally: os.unlink(temp_file.name)`
- Don't rename temp files to fixed names like "tts.mp3"
**Warning signs:** "No such file or directory", garbled audio, permission errors on cleanup

### Pitfall 3: Voice State Update Event Always Fires for Bot's Own State
**What goes wrong:** Auto-leave logic checks for empty channels in on_voice_state_update but triggers when the bot itself moves/connects, causing immediate disconnect.  
**Why it happens:** on_voice_state_update fires for all members including the bot; checking channel members without filtering bot's own state leads to false positives.  
**How to avoid:**
- Always check `if member == bot.user: return` at the start of on_voice_state_update
- Count non-bot members: `non_bot_count = sum(1 for m in vc.channel.members if not m.bot)`
- Only disconnect if `non_bot_count == 0`
**Warning signs:** Bot connects then immediately disconnects; queue is cleared unexpectedly

### Pitfall 4: Blocking Extraction in Event Loop
**What goes wrong:** YoutubeDL.extract_info() takes 2-5 seconds (network + parsing); calling it in a slash command handler blocks all discord events (messages, reactions, voice state updates).  
**Why it happens:** extract_info() is CPU/IO bound; discord.py's event loop is single-threaded and can't process other events while it runs.  
**How to avoid:**
- Always defer the interaction first: `await interaction.response.defer()`
- Run extraction in executor: `url = await bot.loop.run_in_executor(None, lambda: ydl.extract_info(query, process=False))`
- Or use `asyncio.create_task()` for fire-and-forget operations
**Warning signs:** Bot becomes unresponsive to messages/reactions while playing song; commands time out

### Pitfall 5: gTTS Language Code Validation Misses Edge Cases
**What goes wrong:** User sets /tts_lang to an invalid code (e.g., "english" instead of "en"); gTTS fails silently or with cryptic error on next /tts call.  
**Why it happens:** gTTS doesn't validate language codes upfront; it fails at save() time with unhelpful error messages.  
**How to avoid:**
- Maintain a whitelist of supported language codes: `SUPPORTED_LANGS = ['en', 'es', 'fr', ...]` from gTTS documentation
- Validate before storing: `if lang_code not in SUPPORTED_LANGS: raise ValueError(...)`
- Store default 'en' if validation fails
- Log TTS errors with gTTS exception details
**Warning signs:** Intermittent TTS failures; user's language code is garbage; "Bad request" from gTTS

### Pitfall 6: discord.ui.View Timeout and Stale View
**What goes wrong:** Pagination buttons stop working after 15 minutes (default timeout); clicking a button throws "interaction failed" error.  
**Why it happens:** discord.ui.View has a default timeout of 180s (3 min in discord.py, 15 min is misleading); expired views are removed from memory and Discord ignores button clicks.  
**How to avoid:**
- Set explicit timeout based on expected page browsing time: `View(timeout=600.0)` for 10 minutes
- Or handle the error gracefully: if button click fails due to timeout, respond "View expired, use /list_emotes again"
- Consider re-creating the view on each interaction if timeout is a concern
**Warning signs:** "Failed to send response" after inactivity; buttons click but nothing happens

### Pitfall 7: Not Checking Manage Emojis Permission Before Adding/Removing
**What goes wrong:** User without Manage Emojis permission runs /add_emote; bot crashes or responds with a generic error.  
**Why it happens:** discord.py doesn't auto-check permissions; you must explicitly verify via `interaction.permissions.manage_guild_expressions`.  
**How to avoid:**
- Add `@app_commands.default_permissions(manage_guild_expressions=True)` decorator to /add_emote and /remove_emote
- Or check manually: `if not interaction.permissions.manage_guild_expressions: return error_embed(...)`
- Respond with a clear embed before attempting the API call
**Warning signs:** Permission denied errors; command runs but silently fails; users report "unexpected error"

## Code Examples

### Music Queue Display with Pagination
```python
# Source: discord.py ui.View + FFmpegPCMAudio pattern established in CONTEXT.md
import discord
from discord import ui

class QueuePaginationView(ui.View):
    def __init__(self, queue: list[dict], songs_per_page: int = 10):
        super().__init__(timeout=600)
        self.queue = queue
        self.songs_per_page = songs_per_page
        self.current_page = 0
    
    def get_queue_embed(self) -> discord.Embed:
        start = self.current_page * self.songs_per_page
        end = start + self.songs_per_page
        page_songs = self.queue[start:end]
        
        embed = discord.Embed(
            title=f"Queue ({len(self.queue)} songs)",
            description="\n".join(
                f"{i + start + 1}. **{song['title']}** ({song['duration']}s) — <@{song['requester_id']}>"
                for i, song in enumerate(page_songs)
            ) or "Queue is empty",
            color=0x2E7D32  # Phase 1 EMBED_COLOR
        )
        total_pages = (len(self.queue) + self.songs_per_page - 1) // self.songs_per_page or 1
        embed.set_footer(text=f"Page {self.current_page + 1} of {total_pages}")
        return embed
    
    @ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        self.current_page = max(0, self.current_page - 1)
        await interaction.response.edit_message(embed=self.get_queue_embed(), view=self)
    
    @ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        max_pages = (len(self.queue) + self.songs_per_page - 1) // self.songs_per_page or 1
        self.current_page = min(max_pages - 1, self.current_page + 1)
        await interaction.response.edit_message(embed=self.get_queue_embed(), view=self)

@app_commands.command(name="queue")
async def queue_cmd(self, interaction: discord.Interaction) -> None:
    """Display the music queue."""
    await interaction.response.defer()
    view = QueuePaginationView(self.queue)
    embed = view.get_queue_embed()
    await interaction.followup.send(embed=embed, view=view)
```

### TTS with Temp File Cleanup and Language Persistence
```python
# Source: gTTS + aiosqlite + tempfile pattern per CONTEXT.md locked decisions
import asyncio
import os
import tempfile
from gtts import gTTS
from database.db import get_db

class TTSCog(commands.Cog):
    @app_commands.command(name="tts_lang")
    @app_commands.describe(lang_code="ISO 639-1 code (e.g., en, es, fr)")
    async def tts_lang(self, interaction: discord.Interaction, lang_code: str) -> None:
        """Set your preferred TTS language."""
        # Validate against gTTS supported languages
        try:
            # gTTS has a 'lang' attribute with all supported codes
            supported = gTTS(text="test", lang="en").lang  # Get supported languages
            if lang_code not in supported:
                embed = discord.Embed(
                    title="Invalid language code",
                    description=f"`{lang_code}` is not supported. Use ISO 639-1 codes (en, es, fr, etc.)",
                    color=0x2E7D32
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error("Language validation error: %s", e)
            lang_code = "en"  # Fallback to English
        
        # Store in bot_config table (CONTEXT.md locked decision: per-user, persists across restarts)
        async with get_db() as db:
            key = f"tts_lang_{interaction.user.id}"
            await db.execute(
                "INSERT INTO bot_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
                (key, lang_code, lang_code)
            )
        
        embed = discord.Embed(
            title="Language set",
            description=f"TTS language set to `{lang_code}`",
            color=0x2E7D32
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="tts")
    @app_commands.describe(text="Text to speak (max 300 chars)")
    async def tts(self, interaction: discord.Interaction, text: str) -> None:
        """Convert text to speech and play in your voice channel."""
        await interaction.response.defer()
        
        # Validate user is in voice channel (TTS-07)
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(
                title="Error",
                description="You must be in a voice channel",
                color=0x2E7D32
            )
            return await interaction.followup.send(embed=embed)
        
        # Enforce TTS_MAX_CHARS (TTS-06)
        if len(text) > config.TTS_MAX_CHARS:
            embed = discord.Embed(
                title="Text too long",
                description=f"Max {config.TTS_MAX_CHARS} characters",
                color=0x2E7D32
            )
            return await interaction.followup.send(embed=embed)
        
        # Fetch user's language preference (TTS-02)
        async with get_db() as db:
            row = await db.execute_one(
                "SELECT value FROM bot_config WHERE key = ?",
                (f"tts_lang_{interaction.user.id}",)
            )
            lang = row["value"] if row else "en"
        
        # Generate temp file with gTTS (TTS-04)
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(temp_file.name)
            temp_file.close()
            
            # Queue or interrupt based on config (TTS-05)
            if config.TTS_INTERRUPTS_MUSIC:
                # Interrupt: stop current playback
                if interaction.guild.voice_client:
                    interaction.guild.voice_client.stop()
            else:
                # Queue: wait for current music to finish
                # (Handled by MusicCog's on_song_end callback or TTS queue)
                pass
            
            # Play audio (TTS-01)
            vc = interaction.guild.voice_client or await interaction.user.voice.channel.connect()
            source = discord.FFmpegPCMAudio(temp_file.name)
            
            def on_tts_end(error):
                if error:
                    logger.error("TTS playback error: %s", error)
                # Cleanup temp file in finally block below
            
            vc.play(source, after=on_tts_end)
            await interaction.followup.send("Playing TTS...")
        
        except Exception as e:
            logger.error("TTS error: %s", e, exc_info=True)
            embed = discord.Embed(
                title="TTS Error",
                description="Failed to generate speech",
                color=0x2E7D32
            )
            await interaction.followup.send(embed=embed)
        
        finally:
            # Always cleanup temp file (TTS-04: try/finally cleanup)
            if temp_file:
                try:
                    os.unlink(temp_file.name)
                except Exception as e:
                    logger.warning("Failed to clean up temp file: %s", e)
```

### Emoji Proxy with Fuzzy Matching
```python
# Source: discord.py emoji API + difflib pattern per CONTEXT.md EMO-05
import aiofiles
import httpx
from difflib import get_close_matches

class EmojiCog(commands.Cog):
    @app_commands.command(name="emote")
    @app_commands.describe(name="Emoji name")
    async def emote(self, interaction: discord.Interaction, name: str) -> None:
        """Repost emoji as clean message."""
        await interaction.response.defer()
        
        # Exact name match
        emoji_dict = {e.name: e for e in interaction.guild.emojis}
        if name in emoji_dict:
            emoji = emoji_dict[name]
        else:
            # Fuzzy match (EMO-05: difflib.get_close_matches)
            matches = get_close_matches(name, emoji_dict.keys(), n=3, cutoff=0.6)
            if not matches:
                embed = discord.Embed(
                    title="Emoji not found",
                    description=f"No emoji named `{name}` found",
                    color=0x2E7D32
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)
            
            emoji = emoji_dict[matches[0]]
            embed = discord.Embed(
                title="Did you mean?",
                description=f"Closest match: {emoji.mention} (`{emoji.name}`)\n\nOther options: {', '.join(f'`{m}`' for m in matches[1:])}",
                color=0x2E7D32
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Repost as clean message (EMO-01)
        msg = await interaction.channel.send(f"[{interaction.user.display_name}]: {emoji}")
        await interaction.delete_original_response()
    
    @app_commands.command(name="add_emote")
    @app_commands.default_permissions(manage_guild_expressions=True)
    @app_commands.describe(
        name="Emoji name (alphanumeric, 2-32 chars)",
        image_url="Direct image URL (PNG/JPG/GIF, <256KB)"
    )
    async def add_emote(self, interaction: discord.Interaction, name: str, image_url: str) -> None:
        """Add custom emoji to server."""
        await interaction.response.defer()
        
        # Validate name format
        if not (2 <= len(name) <= 32) or not name.replace("_", "").isalnum():
            embed = discord.Embed(
                title="Invalid emoji name",
                description="Name must be 2-32 alphanumeric characters (underscores allowed)",
                color=0x2E7D32
            )
            return await interaction.followup.send(embed=embed)
        
        # Download and validate image (EMO-02: check size + format before upload)
        try:
            async with httpx.AsyncClient() as client:
                # HEAD request for size check (EMO-02: <256KB)
                head = await client.head(image_url, follow_redirects=True)
                content_length = int(head.headers.get("content-length", 0))
                if content_length > 256 * 1024:  # 256KB
                    embed = discord.Embed(
                        title="Image too large",
                        description=f"Max 256KB, got {content_length // 1024}KB",
                        color=0x2E7D32
                    )
                    return await interaction.followup.send(embed=embed)
                
                # GET request for image data (EMO-02: validate PNG/JPG/GIF)
                img_response = await client.get(image_url, follow_redirects=True)
                img_data = img_response.content
                content_type = img_response.headers.get("content-type", "").lower()
                
                if not any(t in content_type for t in ["image/png", "image/jpeg", "image/gif"]):
                    embed = discord.Embed(
                        title="Invalid image format",
                        description="Only PNG, JPG, and GIF are supported",
                        color=0x2E7D32
                    )
                    return await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error("Image download error: %s", e)
            embed = discord.Embed(
                title="Download error",
                description="Failed to download image",
                color=0x2E7D32
            )
            return await interaction.followup.send(embed=embed)
        
        # Create custom emoji (EMO-02)
        try:
            emoji = await interaction.guild.create_custom_emoji(
                name=name,
                image=img_data
            )
            embed = discord.Embed(
                title="Emoji added",
                description=f"{emoji.mention} `:{emoji.name}:`",
                color=0x2E7D32
            )
            await interaction.followup.send(embed=embed)
        
        except discord.HTTPException as e:
            logger.error("Emoji creation error: %s", e)
            embed = discord.Embed(
                title="Failed to create emoji",
                description="Check server emoji limit or name conflicts",
                color=0x2E7D32
            )
            await interaction.followup.send(embed=embed)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| youtube-dl (original) | yt-dlp fork | ~2021 | More reliable extraction, active maintenance, streaming support without temp files |
| Blocking extract_info() in command handler | Async extraction via run_in_executor() or asyncio.create_task() | discord.py 2.0 (2022) | Responsive bot, no event loop blocking |
| Hardcoded TTS languages list | gTTS.lang property or maintained whitelist | gTTS 2.4+ | Dynamic support for new languages, avoids hardcoding maintenance |
| discord-music-player library for queue management | Native VoiceClient.play() + list-based queue | discord.py 2.7 (2024) | More control, fewer dependencies, easier debugging |
| discord-py-slash-command package | discord.py app_commands (built-in) | discord.py 2.0 (2022) | Native slash commands, no third-party library needed |
| Message-based pagination | discord.ui.View with buttons | discord.py 2.0 (2022) | Better UX, cleaner interaction handling, timeout support |

**Deprecated/outdated:**
- youtube_dl (original): Unmaintained since 2019; yt-dlp is the active fork
- discord-music-player: Abstracts VoiceClient details; harder to debug voice issues; yt-dlp + native VoiceClient is now standard
- Synchronous temp file cleanup: Race conditions on concurrent requests; use try/finally with explicit os.unlink()

## Open Questions

1. **yt-dlp Format Selection Exact Params**
   - What we know: CONTEXT.md left format selection to Claude's discretion; bestaudio vs bestvideo+bestaudio tradeoff exists
   - What's unclear: Whether to include prefer_ffmpeg flag, postprocessor args, or just use yt-dlp defaults
   - Recommendation: Start with yt-dlp defaults (`format='bestaudio'` for audio-only), handle errors at playback time. Adjust if FFmpeg issues arise.

2. **TTS Queue vs. Interrupt Boundary**
   - What we know: TTS_INTERRUPTS_MUSIC env var controls behavior; locked decision requires FIFO queue
   - What's unclear: If music is paused (not stopped), should TTS still interrupt? Should TTS interrupt other TTS?
   - Recommendation: TTS_INTERRUPTS_MUSIC controls only music interruption; TTS always interrupts other TTS (FIFO queue handles fairness). Paused music counts as "music playing."

3. **Emoji Validation: Image Size Check Timing**
   - What we know: Content-Length header available via httpx HEAD request; Discord has a 256KB guild emoji limit
   - What's unclear: Should we validate Content-Length or always download and check actual size? What if Content-Length header is missing?
   - Recommendation: Always download the first 256KB to validate actual size; don't rely on Content-Length header alone (can be spoofed). Store full image in memory.

4. **Auto-Leave Rate Limiting**
   - What we know: on_voice_state_update fires for every member state change (mute, deafen, channel change); auto-leave logic runs on channel empty
   - What's unclear: Should we throttle auto-leave checks or add cooldown to prevent rapid reconnect loops?
   - Recommendation: Simple approach: check once per on_voice_state_update, no throttling. Log disconnect events to prevent infinite loops in debugging.

## Environment Availability

**Step 2.6 Status:** SKIPPED (no external dependencies beyond Python, ffmpeg, and Discord)

Phase 2 requires:
- Python 3.11+ (project standard)
- ffmpeg (system dependency for discord.py voice, yt-dlp, gTTS)
- Discord bot token and server setup (Phase 1 prerequisite)
- Network access (yt-dlp YouTube extraction, gTTS cloud API, Discord API)

All required Python packages are in requirements.txt with pinned versions. No additional environment setup needed beyond Phase 1 foundation.

## Validation Architecture

**Validation Architecture Status:** DISABLED

Per `.planning/config.json`, `workflow.nyquist_validation: false` — skipping automated test framework requirements. Cogs will be manually validated through:
- Slash command invocation in test Discord server
- Audio playback verification (queue, skip, pause, resume, volume, seek, loop)
- TTS audio generation and temp file cleanup
- Emoji creation, lookup (exact + fuzzy match), and deletion
- Voice channel auto-leave (disconnect when last user leaves)

No automated test suite required for Phase 2 execution.

## Sources

### Primary (HIGH confidence)
- Discord.py GitHub repository (discord.py 2.7.1 voice client API and VoiceClient patterns)
- yt-dlp GitHub (YoutubeDL class, extract_info() method, format selection)
- gTTS PyPI and GitHub (gTTS class, save() method, supported languages)
- aiosqlite GitHub (async context manager pattern, connection management)
- Python tempfile documentation (NamedTemporaryFile with delete=False)
- discord.py examples/basic_voice.py (FFmpegPCMAudio + PCMVolumeTransformer pattern)

### Secondary (MEDIUM confidence)
- [Python Examples of discord.FFmpegPCMAudio](https://www.programcreek.com/python/example/107433/discord.FFmpegPCMAudio) — FFmpegPCMAudio initialization and volume control
- [Audio Playback - Discord.py Masterclass](https://fallendeity.github.io/discord.py-masterclass/audio-playback/) — Discord.py voice client patterns
- [A walkthrough on action based pagination in discord.py](https://gist.github.com/InterStella0/454cc51e05e60e63b81ea2e8490ef140) — discord.ui.View pagination example
- [Discord.py slash commands guide](https://fallendeity.github.io/discord.py-masterclass/slash-commands/) — app_commands interaction pattern
- [yt-dlp Python API examples](https://www.hrekov.com/blog/youtube-metadata-python-yt-dlp) — YoutubeDL usage for metadata extraction
- [Building a Multilingual Text-to-Speech Tool with Python and gTTS](https://www.tdworakowski.com/2024/11/building-multilingual-text-to-speech-tool.html) — gTTS language codes and save pattern

### Tertiary (LOW confidence)
- [How Can I create a queue for my music bot?](https://github.com/Rapptz/discord.py/discussions/6971) — Community discussion on queue implementation (may have outdated advice)
- [Bot joins the channel but plays no sound](https://github.com/Rapptz/discord.py/discussions/9652) — Common FFmpeg reconnection issues (unverified fixes)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Version numbers verified against requirements.txt (as of 2026-03-31); all libraries actively maintained
- Architecture patterns: HIGH — Patterns from official discord.py documentation, CONTEXT.md locked decisions, Phase 1 foundation established
- Pitfalls: MEDIUM-HIGH — Sourced from official docs (URL expiry, file cleanup) and community issues (reconnect flags, event loop blocking); edge cases may exist
- Code examples: HIGH — Based on discord.py official examples and CONTEXT.md specifications

**Research date:** 2026-03-31  
**Valid until:** 2026-04-30 (yt-dlp updates weekly; discord.py updates monthly; gTTS stable)

**Known limitations:**
- yt-dlp format string syntax not fully researched (LEFT TO DISCRETION in CONTEXT.md)
- TTS queue/interrupt boundary case (paused music) not definitively resolved
- Emoji image validation timing tradeoff not field-tested
- Auto-leave rate limiting question left open

