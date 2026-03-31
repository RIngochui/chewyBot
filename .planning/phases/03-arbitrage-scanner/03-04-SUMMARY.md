---
phase: 03-arbitrage-scanner
plan: 04
subsystem: detection
tags: [arb-detector, ev-detector, signals, tdd, pydantic]

# Dependency graph
requires:
  - phase: 03-arbitrage-scanner
    provides: "NormalizedOdds (models/odds.py), no_vig_probability (utils/odds_math.py)"
  - phase: 03-arbitrage-scanner
    provides: "ArbSignal, EVSignal (models/signals.py)"
  - phase: 03-arbitrage-scanner
    provides: "normalize() (services/odds_normalizer.py)"
provides:
  - "detect_arb(normalized, min_arb_pct, bankroll) in services/arb_detector.py"
  - "detect_ev(normalized, min_ev_pct) in services/arb_detector.py"
  - "INSERT_ARB_SIGNAL, INSERT_EV_SIGNAL SQL constants in database/queries.py"
  - "SELECT_LATEST_ARB_SIGNALS, SELECT_LATEST_EV_SIGNALS SQL constants in database/queries.py"
affects: [03-05-arb-cog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD: RED (17 failing tests) → GREEN (17 passing tests)"
    - "defaultdict grouping by (event_id, market_type) for arb and EV detection"
    - "Per-selection no_vig fair probability using average odds across books"

key-files:
  created:
    - services/test_arb_detector.py
  modified:
    - services/arb_detector.py
    - database/queries.py

key-decisions:
  - "EV fair probability uses per-selection average odds across all books fed into no_vig_probability — avoids mixing all selections together in no_vig call"
  - "detect_arb uses first two selections from ordered dict for 2-outcome markets — correct for h2h markets"

patterns-established:
  - "detect_arb signature: (normalized: list[NormalizedOdds], min_arb_pct: float, bankroll: float) -> list[ArbSignal]"
  - "detect_ev signature: (normalized: list[NormalizedOdds], min_ev_pct: float) -> list[EVSignal]"

requirements-completed: [ARB-08, ARB-09, ARB-10]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 3 Plan 04: Arb Detector Summary

**detect_arb() and detect_ev() implemented with sum(1/best_odds) arb detection and per-selection no-vig EV computation; four SQL constants added to queries.py for signal persistence**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-31
- **Completed:** 2026-03-31
- **Tasks:** 2 (1 TDD + 1 SQL)
- **Files created:** 1 (test file)
- **Files modified:** 2 (arb_detector.py, queries.py)

## Accomplishments

- Implemented `detect_arb()` in services/arb_detector.py: groups records by (event_id, market_type), finds best odds per selection across books, computes arb_pct and proportional stakes
- Implemented `detect_ev()` in services/arb_detector.py: computes per-selection no-vig fair probability (averaging odds across books), yields EVSignal when ev_pct >= threshold
- Added 4 SQL constants to database/queries.py: `INSERT_ARB_SIGNAL`, `INSERT_EV_SIGNAL`, `SELECT_LATEST_ARB_SIGNALS`, `SELECT_LATEST_EV_SIGNALS`
- 17 tests covering arb detection, no-arb cases, EV detection, no-EV cases — all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — failing tests** - `e091ae0` (test)
2. **Task 1: GREEN — implementation** - `053a4b3` (feat)
3. **Task 2: SQL constants** - `54fe0c0` (feat)

_Note: TDD task had two commits (test → feat)_

## Files Created/Modified

- `services/arb_detector.py` — Full implementation of detect_arb() and detect_ev(); replaced NotImplementedError stubs
- `services/test_arb_detector.py` — 17 tests across 4 test classes
- `database/queries.py` — Appended 4 SQL constants (INSERT_ARB_SIGNAL, INSERT_EV_SIGNAL, SELECT_LATEST_ARB_SIGNALS, SELECT_LATEST_EV_SIGNALS)

## Overall Verification Results

```
Arb signals found: 2
  Los Angeles Lakers @ Golden State Warriors: 10.10% arb
  Boston Bruins @ Toronto Maple Leafs: 1.10% arb
EV signals found: 3
All verification checks passed.
```

## Decisions Made

- EV fair probability: Per-selection average odds across all books is fed into `no_vig_probability()`. This gives each selection its own consensus fair probability, which is then checked against each book's offered line. Computing no_vig over all 4 records mixed together gave incorrect results (selections pooled together).
- detect_arb uses ordered dict's first two selections for building the ArbSignal. Correct for 2-outcome (h2h) markets; plan spec targets h2h.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed EV fair probability grouping**
- **Found during:** Task 1 GREEN phase (tests: test_finds_positive_ev_opportunity, test_ev_signal_has_correct_structure)
- **Issue:** Initial implementation called `no_vig_probability()` on all 4 records' odds together (both selections from both books), giving incorrect per-selection fair probabilities
- **Fix:** Group odds per selection (averaging across books), call no_vig on per-selection averages, then map fair_prob back by selection_name before computing ev_pct per record
- **Files modified:** services/arb_detector.py
- **Verification:** All 17 tests pass; book_b Team X at 2.20 correctly yields +EV vs fair prob

---

**Total deviations:** 1 auto-fixed (1 bug in EV algorithm)
**Impact on plan:** Correct ev_pct values. No API signature changes.

## Issues Encountered

None.

## Known Stubs

None — both detect_arb() and detect_ev() are fully implemented. The four SQL constants in queries.py are real INSERT/SELECT statements ready to use in cogs/arb.py (Plan 05).

## Next Phase Readiness

- detect_arb() and detect_ev() ready to be called from cogs/arb.py (Plan 05)
- SQL constants importable: `from database.queries import INSERT_ARB_SIGNAL, INSERT_EV_SIGNAL, SELECT_LATEST_ARB_SIGNALS, SELECT_LATEST_EV_SIGNALS`
- Mock data produces 2 arb signals (10.1% NBA, 1.1% NHL) and 3 EV signals

---
*Phase: 03-arbitrage-scanner*
*Completed: 2026-03-31*
