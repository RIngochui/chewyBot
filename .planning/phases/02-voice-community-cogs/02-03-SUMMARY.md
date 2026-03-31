---
phase: 02-voice-community-cogs
plan: "03"
subsystem: tts
tags: [gtts, discord.py, asyncio, sqlite, tts, voice, bot_config]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: database/queries.py with UPSERT_BOT_CONFIG and GET_BOT_CONFIG_KEY, get_db() context manager, config.py with TTS_MAX_CHARS and TTS_INTERRUPTS_MUSIC, EMBED_COLOR

provides:
  - TTSCog with /tts, /tts_lang, /tts_stop slash commands
  - FIFO asyncio.Queue for TTS requests
  - Per-user language persistence in bot_config via tts_lang_{user_id} key
  - UPSERT_TTS_LANG and GET_TTS_LANG SQL constants in database/queries.py
  - Temp file generation via NamedTemporaryFile with try/finally cleanup

affects:
  - 02-voice-community-cogs
  - MusicCog (TTS_INTERRUPTS_MUSIC bool affects interaction when both cogs active)

# Tech tracking
tech-stack:
  added: [gtts, gtts.lang.tts_langs]
  patterns:
    - gTTS generation in thread executor (asyncio.get_event_loop().run_in_executor)
    - FIFO asyncio.Queue with _is_tts_active guard for sequential queue draining
    - NamedTemporaryFile with delete=False + try/finally os.remove for safe temp cleanup
    - per-user DB key pattern: f"tts_lang_{user_id}" in bot_config table

key-files:
  created: []
  modified:
    - cogs/tts.py
    - database/queries.py

key-decisions:
  - "FIFO asyncio.Queue (not rejection) for concurrent TTS requests — consistent with music queue, better UX"
  - "tts_lang_{user_id} key in bot_config table — no new table needed, persists across restarts"
  - "UPSERT_TTS_LANG uses DO UPDATE SET (not DO NOTHING) so users can change their language"
  - "gTTS runs in thread executor to avoid blocking the Discord event loop"
  - "NamedTemporaryFile with delete=False + try/finally cleanup — OS-managed path, cleanup guaranteed"

patterns-established:
  - "Pattern 1: Thread executor for CPU/IO blocking calls — loop.run_in_executor(None, sync_fn, args)"
  - "Pattern 2: asyncio.Event + call_soon_threadsafe for bridging voice after-callback to async wait"
  - "Pattern 3: FIFO queue with active guard (_is_tts_active) prevents concurrent queue drainers"

requirements-completed: [TTS-01, TTS-02, TTS-03, TTS-04, TTS-05, TTS-06, TTS-07]

# Metrics
duration: 7min
completed: "2026-03-31"
---

# Phase 02 Plan 03: TTS Cog Summary

**TTSCog with gTTS FIFO queue, per-user language persistence in bot_config, and interrupt/queue behavior via TTS_INTERRUPTS_MUSIC**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-31T04:16:36Z
- **Completed:** 2026-03-31T04:23:22Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Replaced tts.py stub with full 172-line TTSCog implementation covering all 7 TTS requirements
- Added UPSERT_TTS_LANG (DO UPDATE) and GET_TTS_LANG SQL constants to database/queries.py enabling per-user language changes
- FIFO asyncio.Queue drains TTS requests sequentially; TTS_INTERRUPTS_MUSIC flag routes to immediate play or queue

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TTS SQL constants to database/queries.py** - `fdfe36a` (feat)
2. **Task 2: Implement TTSCog in cogs/tts.py** - `5b40a04` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `cogs/tts.py` — Full TTSCog: /tts, /tts_lang, /tts_stop with FIFO queue, temp file cleanup, interrupt behavior
- `database/queries.py` — Added UPSERT_TTS_LANG (DO UPDATE) and GET_TTS_LANG constants

## Decisions Made

- UPSERT_TTS_LANG uses `DO UPDATE SET value = excluded.value` (not DO NOTHING like UPSERT_BOT_CONFIG) — users must be able to change their language preference after initial set
- FIFO asyncio.Queue chosen over rejection — consistent with MusicCog queue pattern, better UX when multiple TTS requests arrive
- gTTS run_in_executor pattern: generates MP3 in thread pool, returns path to async context for playback — prevents event loop blocking during network I/O to gTTS API
- asyncio.Event + loop.call_soon_threadsafe used to bridge the voice client's after-callback (runs in audio thread) to await the playback completion in the async queue drainer

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. gTTS is a pip package (no API key). ffmpeg must be installed on host for FFmpegPCMAudio playback (already documented in project requirements).

## Next Phase Readiness

- TTSCog is complete and ready to load; will be loaded by bot.py alongside MusicCog and EmojiCog
- TTS_INTERRUPTS_MUSIC interaction with MusicCog (02-01) is handled in TTSCog — when True, it calls guild.voice_client.stop() before playing TTS
- Language preference persists across bot restarts via bot_config table

---
*Phase: 02-voice-community-cogs*
*Completed: 2026-03-31*

## Self-Check: PASSED

- FOUND: cogs/tts.py
- FOUND: database/queries.py
- FOUND: 02-03-SUMMARY.md
- FOUND commit: fdfe36a (Task 1)
- FOUND commit: 5b40a04 (Task 2)
