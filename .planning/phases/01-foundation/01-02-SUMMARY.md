---
phase: 01-foundation
plan: "02"
subsystem: api
tags: [pydantic, discord.py, httpx, models, adapters, services, utils]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: config.py with EMBED_COLOR constant
provides:
  - Pydantic v2 BaseModel data layer (Market, OddsSnapshot, NormalizedOdds, ArbSignal, EVSignal, ParlayLeg, Parlay)
  - Abstract SportsbookAdapter interface (adapters/base.py)
  - OddsApiAdapter stub with SUPPORTED_BOOKS (fanduel, draftkings, betmgm, bet365)
  - Service stubs for Phase 3 implementation (odds_normalizer, arb_detector, parlay_engine)
  - Utility stubs for Phase 3/4 implementation (odds_math, formatters)
affects: [03-scanner, 04-parlay, all cogs importing models]

# Tech tracking
tech-stack:
  added: [pydantic v2, httpx, discord.py]
  patterns: [pydantic BaseModel for all data contracts, ABC abstract interface for adapter pattern, NotImplementedError stubs with phase references]

key-files:
  created:
    - models/__init__.py
    - models/odds.py
    - models/signals.py
    - models/parlay.py
    - adapters/__init__.py
    - adapters/base.py
    - adapters/odds_api.py
    - services/__init__.py
    - services/odds_normalizer.py
    - services/arb_detector.py
    - services/parlay_engine.py
    - utils/odds_math.py
    - utils/formatters.py
  modified: []

key-decisions:
  - "Pydantic v2 BaseModel used for all data models — runtime validation and clear error messages on API changes"
  - "ABC abstractmethod for SportsbookAdapter — enforces interface contract on all adapter implementations"
  - "NotImplementedError stubs include phase references (Phase 3/4) and requirement IDs — clear handoff for future executors"
  - "EMBED_COLOR imported directly from config in formatters.py — single source of truth for embed styling"

patterns-established:
  - "Stub pattern: correct type signatures + docstrings with requirement IDs + raise NotImplementedError with message"
  - "Adapter pattern: abstract base class in base.py, concrete implementation in named file (odds_api.py)"
  - "Model separation: raw API data (OddsSnapshot) vs normalized canonical form (NormalizedOdds) vs signals (ArbSignal/EVSignal)"

requirements-completed: [BOT-05, BOT-06, BOT-07, DB-04, DEL-04, DEL-05]

# Metrics
duration: 3min
completed: 2026-03-31
---

# Phase 1 Plan 02: Data Models and Stub Layer Summary

**13-file Pydantic v2 model + stub layer establishing data contracts for the odds scanner (ARB-06/07) and parlay AI (PAR-03/05), with abstract SportsbookAdapter interface and typed utility stubs for Phase 3/4 implementation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-31T03:27:26Z
- **Completed:** 2026-03-31T03:30:11Z
- **Tasks:** 2
- **Files modified:** 13

## Accomplishments

- All 7 Pydantic v2 model classes created with full type hints matching the canonical ARB-06/ARB-07 schema (event_id, market_key slug formats documented)
- Abstract SportsbookAdapter interface established with ABC/abstractmethod, OddsApiAdapter stub ready with 4 supported books and quota tracking hook
- 9 stub files (services + utils + adapters) with NotImplementedError bodies, docstrings referencing requirement IDs, and clear Phase 3/4 handoff markers

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic v2 data models** - `c9977f4` (feat)
2. **Task 2: Adapter interface + service stubs + utility stubs** - `331cb52` (feat)

**Plan metadata:** `0fd353e` (docs: complete plan)

## Files Created/Modified

- `models/__init__.py` - Package init (empty)
- `models/odds.py` - Market, OddsSnapshot, NormalizedOdds Pydantic v2 models
- `models/signals.py` - ArbSignal, EVSignal Pydantic v2 models
- `models/parlay.py` - ParlayLeg, Parlay Pydantic v2 models
- `adapters/__init__.py` - Package init (empty)
- `adapters/base.py` - Abstract SportsbookAdapter interface (ABC)
- `adapters/odds_api.py` - OddsApiAdapter stub implementing SportsbookAdapter
- `services/__init__.py` - Package init (empty)
- `services/odds_normalizer.py` - normalize() stub for Phase 3
- `services/arb_detector.py` - detect_arb() + detect_ev() stubs for Phase 3
- `services/parlay_engine.py` - generate_parlay() stub for Phase 4
- `utils/odds_math.py` - 4 odds math function stubs for Phase 3
- `utils/formatters.py` - 3 Discord embed builder stubs importing EMBED_COLOR

## Decisions Made

- Used Pydantic v2 BaseModel for all models (not dataclasses) — matches PROJECT.md and REQUIREMENTS.md spec, provides runtime validation
- ABC/abstractmethod for SportsbookAdapter instead of Protocol — explicit enforcement on concrete implementations
- Stub docstrings include both ARB/PAR requirement IDs and Phase references — gives future executors unambiguous context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all 13 files created with syntax validation passing.

## Known Stubs

The following intentional stubs exist by design — Phase 3 and Phase 4 will fill these in:

- `adapters/odds_api.py`: get_sports(), get_events(), get_odds() — Phase 3 (ARB-02/04/05)
- `services/odds_normalizer.py`: normalize() — Phase 3 (ARB-06/07)
- `services/arb_detector.py`: detect_arb(), detect_ev() — Phase 3 (ARB-08/10)
- `services/parlay_engine.py`: generate_parlay() — Phase 4 (PAR-03/04)
- `utils/odds_math.py`: american_to_decimal(), decimal_to_american(), implied_probability(), no_vig_probability() — Phase 3 (ARB-11)
- `utils/formatters.py`: build_arb_embed(), build_ev_embed(), build_parlay_embed() — Phase 3/4 (ARB-20/21, PAR-10)

These stubs are intentional scaffolding. They do not prevent this plan's goal (establishing importable data contracts) from being achieved.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All data contracts are defined and importable (via AST-valid Python files)
- Phase 3 executor can implement services/arb_detector.py, services/odds_normalizer.py, utils/odds_math.py, utils/formatters.py, adapters/odds_api.py against these model definitions
- Phase 4 executor can implement services/parlay_engine.py against Parlay/ParlayLeg models
- config.py (from Plan 01) must exist before `utils/formatters.py` can be runtime-imported (EMBED_COLOR dependency)

## Self-Check: PASSED

- All 13 created files verified present on disk
- Commit c9977f4 (Task 1 models) verified in git log
- Commit 331cb52 (Task 2 stubs) verified in git log

---
*Phase: 01-foundation*
*Completed: 2026-03-31*
