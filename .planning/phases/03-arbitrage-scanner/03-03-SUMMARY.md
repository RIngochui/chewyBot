---
phase: 03-arbitrage-scanner
plan: 03
subsystem: api
tags: [odds-normalizer, pydantic, odds-api, arb-scanner]

# Dependency graph
requires:
  - phase: 03-arbitrage-scanner
    provides: "NormalizedOdds model (models/odds.py), decimal_to_american (utils/odds_math.py)"
provides:
  - "normalize(event, sport_key, league, supported_books) in services/odds_normalizer.py"
  - "ARB-07 canonical event_id and market_key slug generation"
  - "One NormalizedOdds record per (bookmaker, market, outcome) tuple"
affects: [03-04-arb-detector, 03-05-arb-cog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_slug() helper: lowercased, spaces/hyphens to underscores"
    - "TDD: RED (24 failing tests) → GREEN (24 passing tests)"

key-files:
  created:
    - services/test_odds_normalizer.py
  modified:
    - services/odds_normalizer.py

key-decisions:
  - "market_key encodes event+market_type+selection (not book) — book is a separate field; keys are unique within a book, not globally"
  - "Test for market_key uniqueness scoped to single-bookmaker records to match plan spec"
  - "supported_books=None means include all; supported_books=[] means include none"

patterns-established:
  - "normalize() signature: (event: dict, sport_key: str, league: str, supported_books: list[str] | None = None)"
  - "event_id format: slug(home_team)_slug(away_team)_YYYYMMDD"
  - "market_key format: event_id_slug(market_type)_slug(selection_name)"

requirements-completed: [ARB-06, ARB-07]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 3 Plan 03: Odds Normalizer Summary

**normalize() converts raw Odds API event dicts to typed NormalizedOdds records using ARB-07 slug keys (event_id: home_away_YYYYMMDD, market_key: event_id_market_selection)**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-31T05:13:52Z
- **Completed:** 2026-03-31T05:15:51Z
- **Tasks:** 1 (TDD)
- **Files modified:** 2

## Accomplishments
- Implemented `normalize(event, sport_key, league, supported_books=None)` in services/odds_normalizer.py
- ARB-07 compliant event_id (`home_away_YYYYMMDD`) and market_key (`event_id_market_selection`) slugs
- 24 tests covering record count, event_id uniqueness, market_key format, decimal/american odds, line_value, and supported_books filter

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — failing tests** - `fd433bf` (test)
2. **Task 1: GREEN — implementation** - `072e7bb` (feat)

**Plan metadata:** (docs commit below)

_Note: TDD task had two commits (test → feat)_

## Files Created/Modified
- `services/odds_normalizer.py` - Full implementation of normalize(); replaced NotImplementedError stub
- `services/test_odds_normalizer.py` - 24 tests across 7 test classes

## Decisions Made
- market_key does NOT include book_name — it encodes event+market+selection only. Two books offering the same market get different records (distinguished by `book_name` field) but the same market_key. This matches the plan spec verbatim.
- Test `test_market_keys_are_unique_across_all_records` was corrected to `test_market_keys_unique_within_same_bookmaker` — the original assertion was wrong given the plan's key format.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected test assertion for market_key uniqueness**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test asserted market_keys globally unique across all records, but plan spec shows market_key = event_id_market_selection (no book prefix), so two books offering the same market will share a market_key
- **Fix:** Narrowed test assertion to uniqueness within a single bookmaker's records
- **Files modified:** services/test_odds_normalizer.py
- **Verification:** 24/24 tests pass
- **Committed in:** 072e7bb (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test assertion)
**Impact on plan:** Correction needed to align test with plan's spec. No behavior change to implementation.

## Issues Encountered
None.

## Known Stubs
None — normalize() is fully implemented and wired to NormalizedOdds and decimal_to_american.

## Next Phase Readiness
- normalize() is complete and ready to be called by the arb detector (Plan 04) and EV detector
- Signature: `normalize(event: dict, sport_key: str, league: str, supported_books: list[str] | None = None) -> list[NormalizedOdds]`
- Returns [] for events with no bookmakers — safe for arb/EV loop

---
*Phase: 03-arbitrage-scanner*
*Completed: 2026-03-31*
