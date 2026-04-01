---
phase: 04-nba-parlay-ai
plan: "03"
subsystem: parlay-cog
tags: [parlay, discord, slash-commands, background-task, sqlite, nba]
dependency_graph:
  requires:
    - services/parlay_engine.py (generate_parlay)
    - utils/formatters.py (build_parlay_embed)
    - database/queries.py (INSERT_PARLAY, INSERT_PARLAY_LEG, UPDATE_PARLAY_MESSAGE_ID, SEED_LEG_TYPE_WEIGHTS, SELECT_ALL_LEG_TYPE_WEIGHTS, SELECT_LATEST_PARLAYS, SELECT_PARLAY_STATS, SELECT_PARLAY_WITH_LEGS)
    - database/db.py (get_db)
    - config.py (PARLAY_CHANNEL_ID, LOG_CHANNEL_ID, PARLAY_POST_TIME, MIN_LEG_SCORE)
    - models/parlay.py (Parlay)
  provides:
    - cogs/parlay.py — ParlayCog with daily loop, 3 slash commands, DB persistence
  affects:
    - cogs/parlay.py (plan 04 — reaction handler will add on_raw_reaction_add listener)
tech_stack:
  added: []
  patterns:
    - discord.ext.tasks.loop with change_interval() for dynamic post time
    - zoneinfo.ZoneInfo("America/New_York") for ET timezone post scheduling
    - cog_load() for seeding and task start (avoids __init__ async restrictions)
    - defer(ephemeral=False) + followup pattern for /parlay public post
    - defer(ephemeral=True) + followup pattern for /parlay_stats, /parlay_history
key_files:
  created: []
  modified:
    - cogs/parlay.py
decisions:
  - "tasks.loop decorator uses module-level _dt alias to construct default time — avoids __import__() hack in decorator argument"
  - "daily_parlay default time is 16:00 UTC (stub placeholder); actual time is set via change_interval() in __init__ using PARLAY_POST_TIME + ET timezone"
  - "SELECT_PARLAY_WITH_LEGS imported but not used in slash commands — kept for wave 4 reaction handler which will need full parlay+legs detail"
  - "parlay_history displays combined_odds as decimal multiplier (e.g. 3.50x) since parlays always have decimal odds >1.0"
metrics:
  duration: "177 seconds"
  completed: "2026-04-01T03:35:47Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 1
---

# Phase 04 Plan 03: ParlayCog Wire-Up Summary

**One-liner:** ParlayCog fully wired — daily ET-scheduled auto-post, 3 slash commands (/parlay, /parlay_stats, /parlay_history), DB persistence with discord_message_id, and 6-type weight seeding on startup.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement ParlayCog with daily task and DB persistence | 4562495 | cogs/parlay.py (modified — stub replaced) |

## What Was Built

### cogs/parlay.py

Full replacement of the `ParlayCog` stub. Key components:

**Module-level constant `_ALL_LEG_TYPES`**
List of all 6 locked taxonomy types (decision A from CONTEXT.md). Used by `cog_load()` for seeding.

**`__init__(self, bot)`**
Parses `config.PARLAY_POST_TIME` ("HH:MM"), resolves ET timezone via `zoneinfo.ZoneInfo("America/New_York")` with UTC fallback, constructs a `datetime.time` object, and calls `self.daily_parlay.change_interval(time=[post_time])` to override the stub UTC default.

**`cog_load(self)`**
Seeds all 6 leg types into `leg_type_weights` using `SEED_LEG_TYPE_WEIGHTS` (ON CONFLICT DO NOTHING — existing learned weights survive restarts). Starts the daily task.

**`cog_unload(self)`**
Cancels `daily_parlay` task on cog unload.

**`daily_parlay` background task**
- Fires at `PARLAY_POST_TIME` (ET) via `tasks.loop` + `change_interval()`
- Calls `generate_parlay(min_leg_score=config.MIN_LEG_SCORE)`
- No-games fallback: logs `"[Parlay] Skipped daily post — fewer than 3 scoreable legs found"` to `LOG_CHANNEL_ID`, returns without posting
- On success: delegates to `_post_and_save_parlay()`

**`_post_and_save_parlay(channel, parlay)`**
Private helper used by both `daily_parlay` and `/parlay`:
1. Builds embed via `build_parlay_embed(parlay, post_date)`
2. Posts to channel, captures `msg.id`
3. Single `get_db()` context: INSERT_PARLAY → get `lastrowid` → UPDATE_PARLAY_MESSAGE_ID → INSERT_PARLAY_LEG for each leg
4. Logs `parlay_id`, `message_id`, leg count, confidence

**`/parlay` (parlay_cmd)**
Manual trigger. Defers publicly (`ephemeral=False`), calls `generate_parlay()`, posts via `_post_and_save_parlay()`, sends ephemeral confirmation. Returns ephemeral error if no legs or channel not found.

**`/parlay_stats`**
Queries `SELECT_PARLAY_STATS` for aggregate totals, `SELECT_ALL_LEG_TYPE_WEIGHTS` for per-type data. Computes hit rate, sorts leg types by hit rate for best/worst, builds embed with overall stats + per-leg-type breakdown. Ephemeral.

**`/parlay_history [n]`**
Clamps n to 1–10, queries `SELECT_LATEST_PARLAYS`, builds embed with one field per parlay showing date, outcome emoji (✅/❌/⏳), leg count, decimal multiplier odds, and confidence score. Ephemeral.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced __import__() in decorator with module-level alias**
- **Found during:** Task 1, writing the @tasks.loop decorator
- **Issue:** Plan suggested using a placeholder UTC time for the decorator default, but using `__import__("datetime")` inline in a decorator argument is valid Python but poor style and harder to read
- **Fix:** Added `import datetime as _dt` at module top level; used `_dt.time(...)` and `_dt.timezone.utc` in the decorator argument directly
- **Files modified:** cogs/parlay.py
- **Commit:** 4562495

None other — plan executed as written.

## Verification Results

All 5 verification checks from the plan passed:
1. `python3 -c "import ast; ast.parse(open('cogs/parlay.py').read()); print('syntax OK')"` — syntax OK
2. `python3 -c "from cogs.parlay import setup"` — no ImportError
3. AST check confirms all 10 required functions/methods exist (ParlayCog, __init__, cog_load, cog_unload, daily_parlay, before_daily_parlay, _post_and_save_parlay, parlay_cmd, parlay_stats, parlay_history, setup)
4. `grep -n "INSERT INTO\|SELECT \*\|UPDATE " cogs/parlay.py` — 0 results (no inline SQL)
5. `grep -n "ZoneInfo\|America/New_York" cogs/parlay.py` — confirmed at line 67

## Known Stubs

None — all three slash commands are fully wired to real DB queries and real parlay generation. The only remaining wave is Plan 04 (reaction handler, PAR-06/PAR-07/PAR-14), which will add an `on_raw_reaction_add` listener to this cog's module.

## Self-Check: PASSED

Files modified:
- /Users/ringochui/Projects/chewyBot/cogs/parlay.py — FOUND

Commits:
- 4562495 — FOUND (feat(04-03): implement ParlayCog with daily task, slash commands, DB persistence)
