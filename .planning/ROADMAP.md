# Roadmap: chewyBot

## Overview

chewyBot is built in four phases that reflect its natural architecture. Phase 1 lays the foundation every other cog depends on: bot entry point, config, database layer, logging, and project deliverables. Phase 2 builds the three community cogs — Music, TTS, and Emoji Proxy — that share the audio infrastructure. Phase 3 delivers the core value of the project: the arbitrage and +EV scanner with adapter pattern, math engine, auto-scan loop, and all slash commands. Phase 4 completes the bot with the NBA Parlay AI, its self-learning weight system, and daily auto-post.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Bot entry point, config, database layer, logging, and all project deliverables (completed 2026-03-31)
- [ ] **Phase 2: Voice & Community Cogs** - Music (yt-dlp), TTS (gTTS), and Emoji Proxy cogs
- [x] **Phase 3: Arbitrage Scanner** - Adapter pattern, odds engine, arb/EV detection, auto-scan, all scanner commands (completed 2026-03-31)
- [x] **Phase 4: NBA Parlay AI** - balldontlie integration, parlay generation, learning system, parlay commands (completed 2026-04-01)

## Phase Details

### Phase 1: Foundation
**Goal**: The bot boots, loads all cogs independently, reads config from env, persists data to SQLite, logs to file and Discord, and all project deliverables exist
**Depends on**: Nothing (first phase)
**Requirements**: BOT-01, BOT-02, BOT-03, BOT-04, BOT-05, BOT-06, BOT-07, DB-01, DB-02, DB-03, DB-04, DEL-01, DEL-02, DEL-03, DEL-04, DEL-05
**Success Criteria** (what must be TRUE):
  1. Bot starts with `python bot.py`, connects to Discord, and posts "chewyBot has logged in!" to LOG_CHANNEL_ID
  2. Killing one cog file (syntax error) does not prevent the remaining cogs from loading
  3. All secrets are read from .env via config.py — no hardcoded values anywhere in the codebase
  4. Database initializes all 8 tables on first run; all SQL lives exclusively in database/queries.py
  5. requirements.txt, .env.example, README.md, and both mock JSON files are present and usable
**Plans**: 3 plans
Plans:
- [ ] 01-PLAN-A.md — Core infrastructure: config.py, utils/logger.py, database/db.py, database/queries.py
- [ ] 01-PLAN-B.md — Pydantic models + stub services/adapters/utils: models/, services/, adapters/, utils/odds_math.py, utils/formatters.py
- [ ] 01-PLAN-C.md — Bot entry point + cog stubs + mock data + deliverables: bot.py, cogs/, mock/, requirements.txt, .env.example, README.md

### Phase 2: Voice & Community Cogs
**Goal**: Users can play music from YouTube, speak text-to-speech in voice channels, and proxy Nitro-free emoji — all three cogs fully functional
**Depends on**: Phase 1
**Requirements**: MUS-01, MUS-02, MUS-03, MUS-04, MUS-05, MUS-06, MUS-07, MUS-08, MUS-09, MUS-10, MUS-11, MUS-12, MUS-13, MUS-14, MUS-15, MUS-16, MUS-17, TTS-01, TTS-02, TTS-03, TTS-04, TTS-05, TTS-06, TTS-07, EMO-01, EMO-02, EMO-03, EMO-04, EMO-05
**Success Criteria** (what must be TRUE):
  1. /play [query] joins the user's voice channel and streams audio; /skip, /pause, /resume, /stop, /queue, /nowplaying all work as described
  2. /tts [text] converts text to audio and plays it in the user's voice channel; temp file is deleted after playback
  3. /emote [name] reposts as "[Username]: <emoji>" and the slash invocation is deleted; /add_emote and /remove_emote enforce the Manage Emojis permission
  4. Bot auto-leaves voice channel when it becomes empty
  5. LOG_CHANNEL_ID receives embed on song start, playlist add, and queue end
**Plans**: 4 plans
Plans:
- [x] 02-01-PLAN.md — MusicCog core: queue state, yt-dlp streaming, /play, /playlist, /skip, /stop, /pause, /resume, /queue, /nowplaying, /volume, auto-leave
- [x] 02-02-PLAN.md — MusicCog complete: /seek, /shuffle, /loop, /remove, /clearqueue, MUS-16 log embeds
- [x] 02-03-PLAN.md — TTSCog + TTS SQL: /tts, /tts_lang, /tts_stop, FIFO queue, temp file cleanup, language persistence
- [x] 02-04-PLAN.md — EmojiCog: /emote, /list_emotes, /add_emote, /remove_emote, pagination, fuzzy matching, image validation

### Phase 3: Arbitrage Scanner
**Goal**: The odds scanner fetches live (or mock) data, detects arb and +EV opportunities above configured thresholds, auto-scans every SCAN_INTERVAL_SECONDS, and posts formatted alerts to ARB_CHANNEL_ID
**Depends on**: Phase 1
**Requirements**: ARB-01, ARB-02, ARB-03, ARB-04, ARB-05, ARB-06, ARB-07, ARB-08, ARB-09, ARB-10, ARB-11, ARB-12, ARB-13, ARB-14, ARB-15, ARB-16, ARB-17, ARB-18, ARB-19, ARB-20, ARB-21, ARB-22
**Success Criteria** (what must be TRUE):
  1. With MOCK_MODE=true, /scan triggers a scan from mock/odds_api_sample.json and posts arb/EV alert embeds to ARB_CHANNEL_ID
  2. Arb alert embeds say "Possible Arbitrage" and include sport, event, market, both sides, arb%, stake, profit, and disclaimer footer
  3. /status shows current config, last scan time, and Odds API quota remaining
  4. Auto-scanner loop fires every SCAN_INTERVAL_SECONDS and does not re-alert the same market_key unless arb_pct improves by >0.2%
  5. /set_bankroll, /set_min_arb, /set_min_ev, and /toggle_sport all update runtime config and persist to bot_config table
**Plans**: 5 plans
Plans:
- [x] 03-01-PLAN.md — odds_math.py + formatters.py: four math helpers and two Discord embed builders
- [x] 03-02-PLAN.md — adapters/odds_api.py: mock mode, live API with per-sport backoff, quota tracking
- [x] 03-03-PLAN.md — services/odds_normalizer.py: raw dict to NormalizedOdds canonical schema
- [x] 03-04-PLAN.md — services/arb_detector.py + queries.py signal SQL: arb/EV detection and DB persistence layer
- [x] 03-05-PLAN.md — cogs/arb.py: ArbCog with auto-scanner loop, dedup, 9 slash commands

### Phase 4: NBA Parlay AI
**Goal**: The bot auto-posts a 3–5 leg NBA parlay daily at PARLAY_POST_TIME, learns from Discord reactions, persists weights across restarts, and filters underperforming leg types after 20+ tracked parlays
**Depends on**: Phase 3
**Requirements**: PAR-01, PAR-02, PAR-03, PAR-04, PAR-05, PAR-06, PAR-07, PAR-08, PAR-09, PAR-10, PAR-11, PAR-12, PAR-13, PAR-14
**Success Criteria** (what must be TRUE):
  1. /parlay generates a 3–5 leg NBA parlay embed with team, market type, line, American odds, combined odds, and confidence score
  2. Bot auto-posts parlay daily at PARLAY_POST_TIME to PARLAY_CHANNEL_ID
  3. Adding ✅ or ❌ reaction updates leg_type_weights in the database; weight changes persist after bot restart
  4. /parlay_stats shows hit rate, total tracked parlays, and best/worst leg types
  5. After 20+ tracked parlays, leg types with < 30% hit rate are automatically filtered from future parlays
**Plans**: 4 plans
Plans:
- [x] 04-01-PLAN.md — BallDontLie adapter (mock+live) + all parlay SQL constants in queries.py
- [x] 04-02-PLAN.md — Parlay engine (5-factor scoring, leg selection) + build_parlay_embed()
- [x] 04-03-PLAN.md — ParlayCog: daily task, /parlay, /parlay_stats, /parlay_history, DB persistence
- [x] 04-04-PLAN.md — Reaction handler + self-learning weight update system (PAR-06/07/08/14)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete   | 2026-03-31 |
| 2. Voice & Community Cogs | 3/4 | In Progress|  |
| 3. Arbitrage Scanner | 5/5 | Complete   | 2026-03-31 |
| 4. NBA Parlay AI | 4/4 | Complete   | 2026-04-01 |

## Backlog

### Phase 999.1: Player Props Parlay Legs (BACKLOG)

**Goal:** Extend the parlay engine to support player prop legs (e.g. LeBron over 25.5 pts) with confidence scoring driven by real player data
**Requirements:** TBD
**Plans:** 0 plans

Notes:
- **BallDontLie** — player game logs, season averages, historical depth (key required, already integrated)
- **ESPN unofficial API** — live scores, box scores, injury/questionable status, roster info (no key, undocumented — treat as best-effort)
- **nba_api / stats.nba.com** — advanced metrics, deep historical stats (no key, rate-limits hard)
- **The Odds API `player_props` market** — actual prop lines + odds (already integrated)
- ESPN injury data is high-value alpha for prop confidence (questionable/out status)
- Add player prop leg type to the existing weight learning system
- ESPN endpoint stability risk — build with fallback so engine degrades gracefully if ESPN changes

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: Multi-Server Support (BACKLOG)

**Goal:** Refactor all single-guild hardcodes so the bot can run in multiple Discord servers with per-guild channel config and data partitioning
**Requirements:** TBD
**Plans:** 0 plans

Notes:
- Remove `copy_global_to` + guild-specific `tree.sync` in `bot.py:83-86` — sync globally instead
- Replace 3 fixed channel ID scalars in `config.py` with a per-guild DB config table
- Add `guild_id` column to all 7 DB tables (`arb_signals`, `ev_signals`, `parlays`, `parlay_legs`, `leg_type_weights`, `bot_config`, `odds_snapshots`) + migration
- Replace all `get_channel(config.X_CHANNEL_ID)` calls across `arb.py`, `parlay.py`, `music.py`, `bot.py` with per-guild lookups
- Fix reaction handler in `parlay.py:341` to check against registered parlay channels for any guild
- Namespace TTS lang prefs as `guild_id:user_id` instead of `user_id` only
- Add `/setup` command for guild admins to register their arb/parlay/log channels
- Auto-scanner background tasks need to fan-out results per guild (or run once + broadcast to all registered channels)

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
