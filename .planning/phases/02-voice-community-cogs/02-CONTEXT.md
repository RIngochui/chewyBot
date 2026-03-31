# Phase 2: Voice & Community Cogs - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 implements three fully functional cogs on top of Phase 1's foundation: MusicCog (yt-dlp streaming, 14 slash commands, queue management, auto-leave), TTSCog (gTTS temp-file audio, 3 slash commands, interrupt/queue behavior), and EmojiCog (Nitro-free proxy, 4 slash commands, fuzzy matching, paginated listing). All three cogs replace their Phase 1 stubs with complete, working implementations. No new infrastructure — all data persistence, config, and logging use the existing Phase 1 layer.

</domain>

<decisions>
## Implementation Decisions

### Music Playback Architecture
- Queue data structure: `list` with `current_index` pointer — enables inspect, shuffle, remove-by-position, and /queue display without complexity of asyncio.Queue
- Unexpected voice disconnect: log error, clear queue state, send notification to channel — no auto-reconnect (avoids infinite loops)
- `/play` while music is playing: queue the new track, respond "Added to queue: X" — consistent with standard Discord bot behavior
- yt-dlp audio delivery: stream directly via `FFmpegPCMAudio` + yt-dlp extractors — no temp disk usage, standard discord.py pattern

### TTS Behavior
- Multiple TTS requests while TTS is playing: FIFO queue — consistent with music queue, better UX than rejection
- `/tts_lang` persistence: per-user in `bot_config` table (key: `tts_lang_{user_id}`) — persists across restarts, reuses existing DB layer
- `TTS_INTERRUPTS_MUSIC=false` behavior: queue TTS after current song finishes, confirm with "TTS queued" message
- Temp file: `tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)` — OS-managed, cleanup via try/finally after playback

### Emoji Proxy Details
- `/list_emotes` pagination: `discord.ui.View` with prev/next buttons, 10 emoji per page — better UX, no page argument needed
- Fuzzy name matching: `difflib.get_close_matches(name, all_names, n=3, cutoff=0.6)` — suggests closest per spec EMO-05
- `/add_emote` image source: URL parameter only — matches spec `[image_url]`, simpler validation
- Slash invocation deletion: delete after successful repost — avoids empty chat gap if repost fails

### Claude's Discretion
- Exact yt-dlp format options (bestaudio/best, prefer_ffmpeg, etc.)
- Per-guild vs per-cog state management patterns
- Error embed color vs informational embed color conventions (inherit Phase 1 EMBED_COLOR)
- Specific queue-full behavior if queue grows extremely large

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py`: `Config` object with `TTS_INTERRUPTS_MUSIC`, `TTS_MAX_CHARS`, `EMBED_COLOR`, `LOG_CHANNEL_ID`, `GUILD_ID` all available
- `database/db.py`: `get_db()` async context manager for per-user TTS language persistence in `bot_config`
- `database/queries.py`: `UPSERT_BOT_CONFIG`, `GET_BOT_CONFIG_KEY` already written — usable for TTS language storage
- `utils/logger.py`: `setup_logging()` wired — each cog gets `logging.getLogger(__name__)`
- `utils/formatters.py`: embed builder stubs (Phase 1) — implement in Phase 2 as needed

### Established Patterns
- Cog structure: `commands.Cog` with `__init__(bot)`, `cog_load()`, `setup(bot)` pattern from stubs
- All slash commands guild-specific via `GUILD_ID` (already handled in `bot.py` setup_hook)
- Error handling: log traceback to file, return user-friendly embed to channel
- Async operations: never block event loop — use `asyncio.create_task` for fire-and-forget, `await` for sequential

### Integration Points
- `cogs/music.py` → `config.py` (EMBED_COLOR, LOG_CHANNEL_ID), `utils/logger.py`
- `cogs/tts.py` → `config.py` (TTS_INTERRUPTS_MUSIC, TTS_MAX_CHARS, EMBED_COLOR), `database/db.py` (lang persistence)
- `cogs/emoji.py` → `config.py` (EMBED_COLOR), no DB needed (server emoji managed via Discord API)
- All cogs: `bot.get_channel(config.LOG_CHANNEL_ID)` for log embeds

</code_context>

<specifics>
## Specific Ideas

- Music auto-leave: `VoiceClient.on_voice_state_update` — check if voice channel members (excluding bot) == 0
- yt-dlp search: use `ytsearch1:{query}` URL prefix for search-by-keyword, direct URL passthrough for URLs
- TTS language codes: ISO 639-1 (e.g., `en`, `es`, `fr`) — validate against gTTS supported languages
- Embed on song start: title, URL, thumbnail (yt-dlp `thumbnail`), duration, "Requested by" field
- `/emote` delete: `interaction.message.delete()` after `interaction.channel.send(f"[{user.display_name}]: {emoji}")`
- `/add_emote` validation: check Content-Length header before download; reject if >256KB or not image/png|jpeg|gif

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
