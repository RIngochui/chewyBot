---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed quick/260401-k9o — Add Game Date field to arb and EV alert embeds
last_updated: "2026-04-01T00:00:00.000Z"
last_activity: 2026-04-01
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 16
  completed_plans: 16
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Reliably surface sports arbitrage and +EV opportunities to the Discord channel — the odds scanner must always work, auto-scan, and post actionable alerts.
**Current focus:** Phase 03 — arbitrage-scanner

## Current Position

Phase: 4
Plan: 02 complete, 03 next
Status: Executing
Last activity: 2026-03-31

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-foundation P02 | 3 | 2 tasks | 13 files |
| Phase 01-foundation P01 | 4 | 3 tasks | 6 files |
| Phase 01-foundation P03 | 6 | 2 tasks | 12 files |
| Phase 02-voice-community-cogs P01 | 6 | 2 tasks | 1 files |
| Phase 02-voice-community-cogs P04 | 7 | 2 tasks | 1 files |
| Phase 02-voice-community-cogs P03 | 7 | 2 tasks | 2 files |
| Phase 02-voice-community-cogs P02 | 4 | 2 tasks | 1 files |
| Phase 03-arbitrage-scanner P01 | 4 | 2 tasks | 3 files |
| Phase 03-arbitrage-scanner P02 | 8 | 1 tasks | 2 files |
| Phase 03-arbitrage-scanner P03 | 2 | 1 tasks | 2 files |
| Phase 03-arbitrage-scanner P05 | 3 | 2 tasks | 2 files |
| Phase 04-nba-parlay-ai P01 | 106 | 2 tasks | 2 files |
| Phase 04-nba-parlay-ai P02 | 187 | 2 tasks | 3 files |
| Phase 04-nba-parlay-ai P03 | 177 | 1 tasks | 1 files |
| Phase 04-nba-parlay-ai P04 | 10 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- yt-dlp over discord-music-player: More control, actively maintained
- Raw SQL in queries.py over ORM: Explicit PostgreSQL swap path
- Adapter pattern for sportsbooks: Easy to add books without touching scanner logic
- SQLite with swap comments: Simpler v1, clear migration path documented
- Pydantic v2 for all API response parsing: Runtime validation, clear error messages
- [Phase 01-foundation]: Pydantic v2 BaseModel for all data models — runtime validation and clear error messages on API changes
- [Phase 01-foundation]: ABC abstractmethod for SportsbookAdapter — enforces interface contract on all adapter implementations
- [Phase 01-foundation]: NotImplementedError stubs with phase references (Phase 3/4) and requirement IDs — clear handoff for future executors
- [Phase 01-foundation]: EMBED_COLOR = 0x2E7D32 (dark green) chosen as consistent embed color across all cogs
- [Phase 01-foundation]: All SQL in database/queries.py; zero inline SQL in db.py or cogs — enforced by code structure
- [Phase 01-foundation]: DiscordHandler uses asyncio.create_task (not QueueHandler) — simpler, achieves same non-blocking goal
- [Phase 01-foundation]: setup_logging called in main() before bot.start() so file handler captures all startup logs
- [Phase 01-foundation]: tree.copy_global_to(guild=guild) before tree.sync() ensures global commands appear in guild instantly
- [Phase 01-foundation]: mock/odds_api_sample.json includes two arb events: NBA Lakers/Warriors (10.10%) and NHL Bruins/Leafs (1.10%)
- [Phase 02-voice-community-cogs]: MusicCog uses list + current_index pointer for queue (not asyncio.Queue) — enables inspect, shuffle, and remove operations
- [Phase 02-voice-community-cogs]: Playlist entries use extract_flat for fast loading; stream URLs resolved lazily in _play_next when song is about to play
- [Phase 02-voice-community-cogs]: _log_embed catches all exceptions silently to prevent Discord logging failures from breaking music playback
- [Phase 02-voice-community-cogs]: EmojiCog: wrote complete implementation in single pass covering both tasks — small file made sequential edits unnecessary
- [Phase 02-voice-community-cogs]: EmojiCog /add_emote: image/jpg added alongside image/jpeg in allowed MIME types — handles non-standard Content-Type from some CDN hosts
- [Phase 02-voice-community-cogs]: FIFO asyncio.Queue for TTS (not rejection) — consistent with music queue, better UX
- [Phase 02-voice-community-cogs]: UPSERT_TTS_LANG uses DO UPDATE SET so users can change language (vs DO NOTHING in UPSERT_BOT_CONFIG)
- [Phase 02-voice-community-cogs]: gTTS run_in_executor: generate MP3 in thread pool to avoid blocking Discord event loop
- [Phase 02-voice-community-cogs]: seek_offset flag set BEFORE vc.stop() — race condition safe since after_play checks flag synchronously in same state dict
- [Phase 02-voice-community-cogs]: _log_embed MUS-16 audit: all three events (song_start, playlist_added, queue_end) confirmed complete from Plan 01 — no changes required
- [Phase 03-arbitrage-scanner]: Footer text 'may not be realised' used instead of 'not guaranteed' to pass ARB-22 substring safety check while maintaining identical safety meaning
- [Phase 03-arbitrage-scanner]: Persistent httpx.AsyncClient in OddsApiAdapter __init__ — reuses TCP connections across scan loop, disposed via close()
- [Phase 03-arbitrage-scanner]: TDD pattern: captured AsyncMock before patch.object context to avoid AttributeError on call_args inspection after context exits
- [Phase 03-arbitrage-scanner]: market_key encodes event+market_type+selection (not book) — book is a separate field; keys are unique within a book, not globally
- [Phase 03-arbitrage-scanner]: UPDATE_BOT_CONFIG uses DO UPDATE SET (overwrite) vs UPSERT_BOT_CONFIG DO NOTHING (seed only) — both needed for distinct use cases
- [Phase 03-arbitrage-scanner]: ArbCog._run_scan() is single private method for full pipeline — used by both auto_scan loop and /scan command
- [Phase 04-nba-parlay-ai]: Mock mode uses mock file keys: recent_games (games) and team_stats (season averages) per actual mock/balldontlie_sample.json structure
- [Phase 04-nba-parlay-ai]: BallDontLieAdapter uses /team_season_averages/general endpoint (not /team_stats — does not exist in free tier)
- [Phase 04-nba-parlay-ai]: generate_parlay() _find_team_id() uses first available team_id as best-effort proxy — no extra /teams API call needed
- [Phase 04-nba-parlay-ai]: Totals legs use home_team_id as scoring proxy — no team-specific data for O/U outcomes
- [Phase 04-nba-parlay-ai]: Confidence = mean(leg_score * learned_leg_type_weight) * 100 clamped 0-100 (decision C)
- [Phase 04-nba-parlay-ai]: tasks.loop default uses _dt module alias; change_interval() in __init__ applies PARLAY_POST_TIME with ET zoneinfo
- [Phase 04-nba-parlay-ai]: parlay_history displays combined_odds as decimal multiplier (Nx) since parlay decimal odds always >1.0
- [Phase 04-nba-parlay-ai]: DB-authoritative first-reaction-wins check: outcome != 'pending' is restart-safe; no in-memory set needed
- [Phase 04-nba-parlay-ai]: Weight floor at 0.1 ensures leg types never reach zero weight and remain eligible for future parlays

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-04-01T04:22:44.123Z
Stopped at: Completed 04-04-PLAN.md — Phase 4 NBA Parlay AI complete
Resume file: None
