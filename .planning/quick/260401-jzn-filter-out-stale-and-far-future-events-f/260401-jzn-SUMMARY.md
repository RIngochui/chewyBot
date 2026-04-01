---
phase: quick
plan: 260401-jzn
subsystem: api
tags: [odds-api, arb-scanner, datetime-filter, config]

requires: []
provides:
  - Configurable time-window filter in _run_scan() that drops stale and far-future events
  - ARB_LOOKBACK_HOURS and ARB_LOOKAHEAD_HOURS optional env vars in Config class
affects: [cogs/arb.py, config.py, arb-scanner]

tech-stack:
  added: []
  patterns: ["Silent pre-filter before detect_arb/detect_ev using configurable time window"]

key-files:
  created: []
  modified:
    - config.py
    - cogs/arb.py

key-decisions:
  - "Used local timedelta alias (_td) inside _run_scan() since timedelta was not in module-level imports — avoids changing import section for a single function"
  - "timezone.utc used directly (already imported at module level) rather than a local alias"
  - "Filter is silent with no logging — keeps scan logs clean in production"

patterns-established:
  - "Time-window filtering: apply after normalize(), before detect_arb/detect_ev — same location for any future pre-filter additions"

requirements-completed: []

duration: 8min
completed: 2026-04-01
---

# Quick Task 260401-jzn: Filter Stale and Far-Future Events Summary

**Configurable time-window filter in ArbCog._run_scan() drops events outside [now-2h, now+24h] before arb/EV detection, eliminating false-positive alerts from past games and pre-posted distant odds**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-01T~04:25Z
- **Completed:** 2026-04-01T~04:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `ARB_LOOKBACK_HOURS: float = 2.0` and `ARB_LOOKAHEAD_HOURS: float = 24.0` to Config class as optional env-overridable fields
- Inserted silent time-window filter block in `_run_scan()` after `all_normalized` is built and before the market_type filter
- All 84 existing tests pass unchanged — no test data used hardcoded past dates that would have broken

## Task Commits

1. **Task 1: Add ARB_LOOKBACK_HOURS and ARB_LOOKAHEAD_HOURS to config.py** - `6b9544a` (feat)
2. **Task 2: Filter all_normalized by start_time window in _run_scan()** - `5150c6c` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `/Users/ringochui/Projects/chewyBot/.claude/worktrees/agent-aa293714/config.py` - Added two optional float fields with inline comments
- `/Users/ringochui/Projects/chewyBot/.claude/worktrees/agent-aa293714/cogs/arb.py` - Added 11-line filter block in _run_scan() using local `_td` alias for timedelta

## Decisions Made

- Used local `_td = timedelta` alias inside the function body because `timedelta` was not already imported at module level — avoids changing the module-level import section for a single usage.
- `timezone.utc` used directly since `timezone` was already imported at module level (`from datetime import datetime, timezone`).
- Filter is silent (no log statements) to keep scan output clean. Dropped events simply disappear before detection.

## Deviations from Plan

The plan's Task 2 verification script used incorrect `NormalizedOdds` constructor arguments (`sport_key`, `sport_title`, `selection`, `book`, `price` fields that don't match the actual Pydantic model). The inline filter logic itself was correct. The deviation was in the verification approach only — the filter logic was tested with correct field names and produced the expected result (2 of 4 test events passing).

**Total deviations:** 0 (plan logic executed exactly as written; verification script adapted to actual model schema)

## Issues Encountered

The plan's verification snippet had outdated `NormalizedOdds` field names (`sport_key`, `selection`, `book`, `price`) that don't match the actual model fields (`sport`, `selection_name`, `book_name`, `decimal_odds`, `american_odds`). Adapted the verification to use correct fields — the filter logic itself was unaffected.

## User Setup Required

None — no external service configuration required. Both new env vars have sensible defaults and can optionally be overridden:
- `ARB_LOOKBACK_HOURS=2.0` (allow events up to 2 hours in the past)
- `ARB_LOOKAHEAD_HOURS=24.0` (ignore events more than 24 hours out)

## Next Phase Readiness

- Arb scanner now filters actionable events only, reducing false-positive Discord alerts
- Time window bounds are configurable per deployment via .env
- No blockers

---
*Phase: quick*
*Completed: 2026-04-01*
