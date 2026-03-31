---
phase: 03-arbitrage-scanner
plan: 05
subsystem: cog
tags: [discord.py, tasks.loop, slash-commands, arb-scanner, ev-scanner, dedup, sqlite, aiosqlite]

# Dependency graph
requires:
  - phase: 03-arbitrage-scanner
    provides: "OddsApiAdapter with mock mode, live API, backoff, quota tracking (adapters/odds_api.py)"
  - phase: 03-arbitrage-scanner
    provides: "normalize() in services/odds_normalizer.py"
  - phase: 03-arbitrage-scanner
    provides: "detect_arb(), detect_ev() in services/arb_detector.py"
  - phase: 03-arbitrage-scanner
    provides: "build_arb_embed(), build_ev_embed() in utils/formatters.py"
  - phase: 03-arbitrage-scanner
    provides: "INSERT_ARB_SIGNAL, INSERT_EV_SIGNAL, SELECT_LATEST_ARB_SIGNALS, SELECT_LATEST_EV_SIGNALS in database/queries.py"
provides:
  - "Complete ArbCog in cogs/arb.py: auto-scanner tasks.loop + 9 slash commands"
  - "Auto-scanner fires every SCAN_INTERVAL_SECONDS from cog_load, never stops on error"
  - "In-memory _seen dedup dict: re-alerts only if arb_pct improves >0.2% (ARB-09)"
  - "All signals persisted to DB on every scan; Discord embeds posted only when above dedup threshold"
  - "/set_* commands persist runtime config changes to bot_config table via UPDATE_BOT_CONFIG"
  - "UPDATE_BOT_CONFIG SQL constant added to database/queries.py (INSERT ... ON CONFLICT DO UPDATE)"
  - "chewyBot Phase 3 core value fully live: auto-scan, alert, persist"
affects:
  - "04-nba-parlay-ai — parlay cog can import OddsApiAdapter for NBA lines reuse"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "tasks.loop with before_loop wait_until_ready — canonical discord.py background task pattern"
    - "try/except Exception in loop body with logger.exception — loop never stops, all errors logged"
    - "In-memory dedup dict (_seen) keyed by market_key for arb, f'ev_{market_key}_{book_name}' for EV"
    - "Defer + followup for commands that call _run_scan — avoids Discord 3s interaction timeout"
    - "cog_unload cancels task and calls adapter.close() — clean shutdown of httpx client"
    - "Runtime config updated in-memory first, then persisted to DB — safe even if DB write fails"

key-files:
  created: []
  modified:
    - "cogs/arb.py — full ArbCog implementation replacing Phase 1 stub"
    - "database/queries.py — added UPDATE_BOT_CONFIG SQL constant"

key-decisions:
  - "UPDATE_BOT_CONFIG uses DO UPDATE SET (overwrite) vs UPSERT_BOT_CONFIG which uses DO NOTHING (seed only) — both needed for distinct use cases"
  - "Dedup key for EV uses f'ev_{market_key}_{book_name}' — market_key alone is not unique across books for EV signals"
  - "_run_scan returns (arb_signals, ev_signals) tuple — enables /scan command to report counts without re-running"
  - "No guild_only() decorator on commands — guild sync is handled centrally in bot.py on_ready"

patterns-established:
  - "ArbCog._run_scan(): single private method for full pipeline — used by both auto_scan loop and /scan command"
  - "Runtime config as instance vars (_bankroll, _min_arb_pct, _min_ev_pct, _enabled_sports) mirroring env defaults"

requirements-completed: [ARB-12, ARB-13, ARB-14, ARB-15, ARB-16, ARB-17, ARB-18, ARB-19]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 03 Plan 05: ArbCog Summary

**Complete ArbCog with tasks.loop auto-scanner, in-memory dedup, signal persistence to SQLite, and 9 slash commands wiring all Phase 3 components into the running Discord bot**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-31T05:25:52Z
- **Completed:** 2026-03-31T05:28:12Z
- **Tasks:** 2 (1 SQL patch + 1 full cog implementation)
- **Files modified:** 2

## Accomplishments

- Added `UPDATE_BOT_CONFIG` SQL constant to `database/queries.py` — `INSERT ... ON CONFLICT DO UPDATE SET` for persistent runtime config changes
- Replaced Phase 1 stub in `cogs/arb.py` with full 300-line ArbCog implementation
- Auto-scanner `tasks.loop` starts in `cog_load`, catches all exceptions, never stops
- `_run_scan` wires the full pipeline: OddsApiAdapter → normalize → detect_arb/detect_ev → persist to DB → post embeds to ARB_CHANNEL_ID
- In-memory `_seen` dict deduplicates Discord alerts — re-alerts only when arb_pct improves by >0.2%
- All 9 slash commands implemented and verified: /ping, /scan, /latest_arbs, /latest_ev, /set_bankroll, /set_min_arb, /set_min_ev, /toggle_sport, /status
- Mock pipeline verified end-to-end: 2 arb signals (10.1% NBA, 1.1% NHL), 3 EV signals — all embeds titled correctly, no "guaranteed" language

## Task Commits

Each task was committed atomically:

1. **Task 1: Add UPDATE_BOT_CONFIG SQL** - `b345ba9` (feat)
2. **Task 2: Implement ArbCog** - `dc71811` (feat)

## Files Created/Modified

- `/Users/ringochui/Projects/chewyBot/cogs/arb.py` — Full ArbCog: auto-scanner loop, _run_scan, _seen dedup, 9 slash commands, setup()
- `/Users/ringochui/Projects/chewyBot/database/queries.py` — Added UPDATE_BOT_CONFIG constant (INSERT ... ON CONFLICT DO UPDATE SET)

## Decisions Made

- **UPDATE_BOT_CONFIG vs UPSERT_BOT_CONFIG:** Both are needed — UPSERT uses DO NOTHING (seed only, preserves operator values), UPDATE uses DO UPDATE SET (intentional overwrite by /set_* commands)
- **EV dedup key:** `f'ev_{market_key}_{book_name}'` — market_key alone is not unique per EV signal since multiple books can have the same market_key with different EV
- **_run_scan returns tuple:** Enables /scan to report found counts without a second scan pass; auto_scan discards return value
- **No guild_only() decorator:** Guild sync is centrally handled in bot.py on_ready; adding per-command sync would conflict

## Deviations from Plan

None — plan executed exactly as written. `UPDATE_BOT_CONFIG` was confirmed absent before adding it. The `cogs/arb.py` implementation follows the plan spec precisely including dedup logic, _run_scan structure, all 9 commands, and setup().

## Issues Encountered

- `python` command not found on macOS (Xcode Python 3.9 only exposes `python3`). All verification commands use `python3`. All plan-specified verification checks pass with `python3`.
- Import chain test requires dummy env vars since config.py fails fast on missing required vars. Set `DISCORD_TOKEN=dummy GUILD_ID=123 ...` in shell before import verification.

## Known Stubs

None — all 9 slash commands are fully implemented. The auto-scanner loop is live and posts to ARB_CHANNEL_ID. Signal persistence is wired. Runtime config persists to bot_config table.

## User Setup Required

The bot requires a `.env` file with real values before running. See `.env.example` for all required and optional variables. Key variables for this cog:
- `DISCORD_TOKEN` — bot token from Discord Developer Portal
- `ODDS_API_KEY` — from https://the-odds-api.com
- `ARB_CHANNEL_ID` — Discord channel ID for arb/EV alerts
- `GUILD_ID` — Discord server ID
- Set `MOCK_MODE=True` for testing without live API calls

## Next Phase Readiness

- Phase 3 core value is complete: auto-scan, alert, persist all working
- Phase 4 (NBA Parlay AI) can reuse `OddsApiAdapter` for NBA lines data
- Checkpoint required: human verification in Discord before marking Phase 3 complete

## Self-Check: PASSED

- FOUND: cogs/arb.py (300+ lines, full ArbCog)
- FOUND: database/queries.py (UPDATE_BOT_CONFIG added)
- FOUND: commit b345ba9 (Task 1: UPDATE_BOT_CONFIG)
- FOUND: commit dc71811 (Task 2: ArbCog implementation)

---
*Phase: 03-arbitrage-scanner*
*Completed: 2026-03-31*
