---
phase: 04-nba-parlay-ai
plan: "01"
subsystem: data-foundation
tags: [balldontlie, adapter, sql, parlay, nba]
dependency_graph:
  requires: [adapters/base.py, database/queries.py, mock/balldontlie_sample.json, config.py]
  provides: [adapters/balldontlie.py, database/queries.py parlay SQL constants]
  affects: [cogs/parlay.py (future), services/parlay_engine.py (future)]
tech_stack:
  added: [httpx (existing), balldontlie free-tier API (keyless)]
  patterns: [OddsApiAdapter pattern, exponential backoff, cursor pagination, MOCK_MODE guard]
key_files:
  created: [adapters/balldontlie.py]
  modified: [database/queries.py]
decisions:
  - "Mock mode uses mock/balldontlie_sample.json keys: recent_games (games), team_stats (season averages)"
  - "get_team_season_averages uses /team_season_averages/general endpoint (not /team_stats — not in free tier)"
  - "Cursor-based pagination capped at 2 pages to stay within 5 req/min rate limit"
metrics:
  duration: "106 seconds"
  completed: "2026-04-01T03:23:13Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 04 Plan 01: NBA Parlay AI Data Foundation Summary

**One-liner:** BallDontLieAdapter (async, mock+live, cursor-paginated) plus 15 parlay SQL constants covering full parlay lifecycle and self-learning leg type weights.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build adapters/balldontlie.py | 5ca58c5 | adapters/balldontlie.py (created) |
| 2 | Add parlay SQL constants to database/queries.py | 732086d | database/queries.py (modified) |

## What Was Built

### adapters/balldontlie.py

`BallDontLieAdapter` following the `OddsApiAdapter` pattern exactly:

- Constructor: `__init__(mock_mode: bool = False)` — keyless, `httpx.AsyncClient(timeout=10.0)`
- `_fetch_with_retry()`: 3 attempts, exponential backoff 1s/2s, returns `None` on all failures (BOT-07)
- `get_games()`: fetches `/v1/games` with `team_ids[]`, `dates[]`, `seasons[]`, `per_page` params; cursor-based pagination (max 2 pages); mock returns `data["recent_games"]`
- `get_team_season_averages()`: fetches `/v1/team_season_averages/general?season=N&team_ids[]=X`; mock returns `data["team_stats"]`
- `close()`: `await self._client.aclose()`

### database/queries.py Phase 4 section

15 new SQL constants appended in two clearly delimited blocks:

**Parlay persistence (8 constants):**
- `INSERT_PARLAY` — insert parlay with generated_at passed explicitly (UTC isoformat)
- `UPDATE_PARLAY_MESSAGE_ID` — set Discord message ID after posting
- `UPDATE_PARLAY_OUTCOME` — mark hit/miss/pending
- `INSERT_PARLAY_LEG` — insert one leg (parlay_id, team, market_type, line_value, american_odds, leg_score, leg_type)
- `SELECT_PARLAY_BY_MESSAGE_ID` — look up parlay row by Discord message ID (reaction handler)
- `SELECT_PARLAY_LEGS` — fetch all legs for a parlay (weight updates)
- `SELECT_LATEST_PARLAYS` — last N parlays ordered by generated_at DESC
- `SELECT_PARLAY_WITH_LEGS` — JOIN query for full parlay + legs detail
- `SELECT_PARLAY_COUNT` — count tracked (non-pending) parlays

**Leg type weight persistence (5 constants):**
- `SEED_LEG_TYPE_WEIGHTS` — INSERT ... ON CONFLICT DO NOTHING (ensures all 6 leg types have rows at startup, PAR-09)
- `SELECT_ALL_LEG_TYPE_WEIGHTS` — load all weights into memory on cog startup
- `SELECT_LEG_TYPE_WEIGHT` — fetch one leg type weight
- `UPSERT_LEG_TYPE_WEIGHT_HIT` — increment hit_count and update weight
- `UPSERT_LEG_TYPE_WEIGHT_MISS` — increment miss_count and update weight
- `SELECT_LOW_HIT_RATE_LEG_TYPES` — find leg types with hit rate < 30% (PAR-08 filter after 20+ parlays)

**Parlay stats (1 constant):**
- `SELECT_PARLAY_STATS` — aggregate hit/miss/total for /parlay_stats command

## Deviations from Plan

### Auto-noted Discrepancies (No Impact)

**1. Mock key names differ from plan text**
- **Found during:** Task 1, while reading mock/balldontlie_sample.json
- **Issue:** Plan text said `data["games"]` and `data["team_season_averages"]` for mock returns, but the mock file uses `"recent_games"` and `"team_stats"` keys respectively
- **Fix:** Used the actual mock file keys (`"recent_games"`, `"team_stats"`) — the mock file is the ground truth for mock data structure. Added comment in code explaining this.
- **Files modified:** adapters/balldontlie.py
- **Impact:** None — downstream plans will work correctly with the actual data returned. No mock file change needed.

## Verification Results

All 4 checks from the plan passed:
1. `from adapters.balldontlie import BallDontLieAdapter` — no ImportError
2. `from database.queries import INSERT_PARLAY, SEED_LEG_TYPE_WEIGHTS` — no ImportError
3. `grep -rn "INSERT INTO parlays" adapters/ cogs/ services/ utils/` — 0 results (no inline SQL)
4. `from adapters.odds_api import OddsApiAdapter` — still imports cleanly

Mock mode test: `get_games()` returned 50 games, `get_team_season_averages()` returned 10 records.

## Known Stubs

None — this plan builds pure infrastructure (adapter and SQL constants). No UI or data rendering is wired yet. Downstream plans (04-02 engine, 04-03 cog) will consume these artifacts.

## Self-Check: PASSED

Files created/modified:
- /Users/ringochui/Projects/chewyBot/adapters/balldontlie.py — FOUND
- /Users/ringochui/Projects/chewyBot/database/queries.py — FOUND (modified)

Commits:
- 5ca58c5 — FOUND (feat(04-01): add BallDontLieAdapter with mock and live modes)
- 732086d — FOUND (feat(04-01): add parlay SQL constants to database/queries.py)
