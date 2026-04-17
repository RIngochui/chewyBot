---
status: complete
quick_id: 260417-ey0
slug: parlay-same-day-filter-and-auto-outcome-
description: parlay same-day filter and auto-outcome check
date: 2026-04-17
commits:
  - 0c07611
  - 2b3fff4
  - e3449fb
---

# Quick Task 260417-ey0: parlay same-day filter and auto-outcome check

## What Was Done

Three atomic commits delivered two improvements to the NBA parlay system.

### Task 1 — SQL queries + mock data (0c07611)

- `database/queries.py`: Added `SELECT_PENDING_PARLAYS_STALE` (pending parlays with `generated_at < NOW - 12 hours`) and `SELECT_PARLAY_LEGS_FULL` (full leg data: id, team, market_type, line_value, leg_type, outcome for a parlay).
- `mock/balldontlie_sample.json`: All 50 `recent_games` entries updated to include `home_team` and `visitor_team` sub-objects with `full_name`, matching the live BallDontLie API shape required by the new name-matching outcome resolver.

### Task 2 — Same-day ET filter + resolve_pending_parlays (2b3fff4)

- `services/parlay_engine.py`: Added ET same-day filter after step 3 odds fetch — drops any odds event whose `commence_time` (UTC) doesn't land on today's date in `America/New_York`. Parlays now only contain legs from games playing today.
- `services/parlay_engine.py`: Added `resolve_pending_parlays()` async function that:
  - Queries DB for stale pending parlays (> 12h old)
  - Derives game date from `parlays.generated_at` (UTC → ET)
  - Fetches Final game results via `BallDontLieAdapter.get_games(dates=[game_date])`
  - Resolves each leg via h2h/spreads/totals logic using fuzzy `_name_matches()` team matching
  - Updates `parlay_legs.outcome`, `parlays.outcome`, and `leg_type_weights` in DB
  - Returns result dicts for Discord posting

### Task 3 — Remove reactions, wire auto-resolution (e3449fb)

- `cogs/parlay.py`: Removed `_NUMBER_EMOJIS`, `_LEG_EMOJI_MAP`, entire `on_raw_reaction_add` listener (~150 lines), and the reaction-adding loop in `_post_and_save_parlay`. Removed all now-unused query imports. `daily_parlay` task now calls `resolve_pending_parlays()` before generating today's parlay and posts a results embed for each resolved parlay.
- `utils/formatters.py`: Updated `build_parlay_embed` footer to "Results will be checked automatically before tomorrow's parlay." Added `build_parlay_result_embed()` that renders yesterday's parlay with per-leg ✅/❌/⏳ emoji and overall HIT/MISS/PENDING outcome.

## Files Changed

- `database/queries.py`
- `mock/balldontlie_sample.json`
- `services/parlay_engine.py`
- `cogs/parlay.py`
- `utils/formatters.py`
