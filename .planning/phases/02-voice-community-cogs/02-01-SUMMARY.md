---
phase: 02-voice-community-cogs
plan: 01
subsystem: music-cog
tags: [music, yt-dlp, voice, discord, ffmpeg, streaming, queue]
dependency_graph:
  requires:
    - config.py (EMBED_COLOR, config.LOG_CHANNEL_ID)
    - utils/logger.py (logging.getLogger pattern)
    - discord.py VoiceClient (FFmpegPCMAudio, PCMVolumeTransformer)
    - yt-dlp (YoutubeDL.extract_info)
    - ffmpeg (system install, required by FFmpegPCMAudio)
  provides:
    - cogs/music.py: MusicCog with 9 slash commands + auto-leave handler
  affects:
    - bot.py (loads MusicCog via cog loader)
tech_stack:
  added:
    - yt-dlp: YouTube audio extraction and metadata (YoutubeDL.extract_info)
    - discord.py VoiceClient: FFmpegPCMAudio + PCMVolumeTransformer for streaming
    - discord.ui.View: QueueView paginated embed with prev/next buttons
  patterns:
    - Per-guild state dict (list + current_index pointer, not asyncio.Queue)
    - run_in_executor for blocking yt-dlp calls (non-blocking event loop)
    - after_play callback uses asyncio.run_coroutine_threadsafe for thread-safe queue advance
    - Flat playlist extraction with deferred stream URL resolution on play
key_files:
  created:
    - cogs/music.py: Full MusicCog implementation (782 lines)
  modified: []
decisions:
  - Queue as list with current_index pointer (per locked decision in CONTEXT.md — enables inspect, shuffle, remove)
  - Stream URL deferred for playlist entries (flat-extracted, resolved only when song is played)
  - _play_next recursion on skip/error rather than vc.stop() loop (cleaner state management)
  - _log_embed catches all exceptions silently (Discord logging failure must not break playback)
metrics:
  duration_minutes: 6
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
  lines_written: 782
---

# Phase 02 Plan 01: MusicCog Implementation Summary

**One-liner:** yt-dlp + FFmpegPCMAudio streaming MusicCog with 9 slash commands, per-guild queue via list+index pointer, auto-leave handler, and LOG_CHANNEL_ID embeds.

## What Was Built

Replaced the stub `cogs/music.py` with a complete `MusicCog` implementation (782 lines). The cog provides full music playback lifecycle management in Discord voice channels.

### Core Architecture

- **Per-guild state dict** (`_guild_state: dict[int, dict]`) keyed by `guild_id`. Each guild's state contains: `queue` (list of song dicts), `current_index` (int pointer), `is_playing` (bool), `volume` (float 0.0–1.0), `loop` ('off'/'song'/'queue'), `channel_id`, and `start_time`.

- **`_fetch_song(url)`** — runs `yt_dlp.YoutubeDL.extract_info()` in `run_in_executor` to avoid blocking the event loop. Handles both direct URLs and keyword searches via the `ytsearch` default_search prefix. Returns a typed song dict or `None` on error.

- **`_fetch_playlist(url)`** — uses `extract_flat="in_playlist"` for fast metadata extraction. Actual stream URLs are resolved lazily in `_play_next` when the song is about to play.

- **`_play_next(guild)`** — core playback loop. Checks voice client state, detects flat-extracted entries needing URL resolution, wraps source in `PCMVolumeTransformer`, and uses `after_play` callback with `run_coroutine_threadsafe` for thread-safe queue advancement.

- **`_log_embed(guild, event_type, song)`** — posts embeds to `config.LOG_CHANNEL_ID` on `song_start`, `queue_end`, and `playlist_added` events. Catches all exceptions silently so logging never breaks playback.

### Commands Implemented

| Command | Requirement | Description |
|---------|-------------|-------------|
| `/play [query]` | MUS-01 | Search or URL; queues if playing, else starts immediately |
| `/playlist [url]` | MUS-02 | Loads all playlist tracks, starts if not playing |
| `/skip` | MUS-03 | Calls `vc.stop()` which triggers after callback to advance index |
| `/stop` | MUS-04 | Stops, clears queue, disconnects voice client |
| `/pause` | MUS-05 | Pauses if playing |
| `/resume` | MUS-06 | Resumes if paused |
| `/queue [page]` | MUS-07 | Paginated embed (10/page) with `QueueView` prev/next buttons |
| `/nowplaying` | MUS-08 | Title, thumbnail, duration, text progress bar (20 chars) |
| `/volume [0-100]` | MUS-09 | Live `PCMVolumeTransformer.volume` mutation |

### Event Handlers

- **`on_voice_state_update`** (MUS-15) — fires on member voice state changes. Ignores bot's own changes and join events. When a member leaves the bot's channel and no non-bot members remain, clears queue state and disconnects.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Enhancement] Playlist entries resolve stream URL at play time**

- **Found during:** Task 1 (_play_next implementation)
- **Issue:** The plan specified `extract_flat="in_playlist"` for playlist extraction, which returns metadata-only entries with page URLs (e.g., `https://youtube.com/watch?v=...`) rather than streaming URLs. Playing these directly with FFmpegPCMAudio would fail.
- **Fix:** Added `_resolve_stream_url()` helper and detection logic in `_play_next` that identifies page URLs (containing `youtube.com` or `youtu.be`) and resolves them to actual stream URLs via `_fetch_song` before playback.
- **Files modified:** `cogs/music.py`
- **Commit:** 95f69ef

**2. [Rule 2 - Enhancement] /play "Added to queue" position calculation**

- **Found during:** Task 1 (/play command)
- **Issue:** Plan said "append to queue, followup with 'Added to queue: X' (position in queue shown)" but the position calculation needed to account for `current_index` to show true queue position.
- **Fix:** Position computed as `len(state['queue']) - state['current_index']` to show position relative to current playback point.
- **Files modified:** `cogs/music.py`
- **Commit:** 95f69ef

## Known Stubs

None — all 9 commands are fully implemented with real logic.

## Self-Check: PASSED

**Files exist:**
- `cogs/music.py`: FOUND

**Commits exist:**
- `95f69ef`: FOUND (feat(02-01): implement MusicCog with full state management and playback commands)

**Acceptance criteria met:**
- Syntax: PASSED
- Command count (>= 9): 9 PASSED
- FFmpegPCMAudio: FOUND
- PCMVolumeTransformer: FOUND
- yt_dlp: FOUND
- on_voice_state_update: FOUND
- _get_state: FOUND
- current_index: FOUND
- run_in_executor: FOUND
- _log_embed: FOUND
- No tempfile: PASSED
- No inline SQL: PASSED
- Lines > 300: 782 PASSED
