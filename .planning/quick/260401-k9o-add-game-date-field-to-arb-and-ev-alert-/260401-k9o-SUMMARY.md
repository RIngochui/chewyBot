---
phase: quick
plan: 260401-k9o
subsystem: arbitrage-scanner
tags: [arb, ev, embeds, datetime, formatting]
dependency_graph:
  requires: []
  provides: [game_time field on ArbSignal/EVSignal, Game Date embed field]
  affects: [utils/formatters.py, models/signals.py, services/arb_detector.py]
tech_stack:
  added: [zoneinfo.ZoneInfo]
  patterns: [optional field with None default, conditional embed field]
key_files:
  created: []
  modified:
    - models/signals.py
    - services/arb_detector.py
    - utils/formatters.py
decisions:
  - "Game Date field placed after Event field (inline=True) so it rows with Sport+Event in Discord embed layout"
  - "strftime format '%-I:%M %p ET, %a %b %-d %Y' produces '7:30 PM ET, Sun Apr 5 2026' — no leading zeros, human-readable"
  - "game_time=None default preserves backward compatibility for DB-loaded signals"
metrics:
  duration: 8m
  completed: 2026-04-01
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 260401-k9o: Add Game Date Field to Arb and EV Alert Embeds Summary

**One-liner:** Added optional `game_time` field to `ArbSignal`/`EVSignal` and conditional ET-formatted "Game Date" embed field to both arb and EV alert builders.

## What Was Built

Arb and EV alert Discord embeds previously had no timing information — users couldn't tell if an opportunity was for tonight's game or next week. This task adds a "Game Date" inline field showing the game's scheduled time in Eastern Time.

The implementation has three layers:

1. **Model layer** (`models/signals.py`): Added `game_time: Optional[datetime] = None` as the last field on both `ArbSignal` and `EVSignal`. Defaults to `None` so existing DB-loaded signals remain valid with no migration needed.

2. **Detection layer** (`services/arb_detector.py`): Both signal constructors now pass `game_time` from the source `NormalizedOdds` record's `start_time`. For arb signals, `records[0].start_time` is used (all records in a group share the same event start time). For EV signals, `rec.start_time` is used per iteration.

3. **Formatter layer** (`utils/formatters.py`): Both `build_arb_embed` and `build_ev_embed` conditionally insert a "Game Date" inline field after the "Event" field when `signal.game_time is not None`. The UTC-aware datetime is converted to Eastern Time via `ZoneInfo("America/New_York")` and formatted as `"%-I:%M %p ET, %a %b %-d %Y"` (e.g. "7:30 PM ET, Sun Apr 5 2026").

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add game_time field to ArbSignal/EVSignal, wire in arb_detector | 29b4139 | models/signals.py, services/arb_detector.py |
| 2 | Add Game Date field to build_arb_embed and build_ev_embed | fd7ff4a | utils/formatters.py |

## Verification

- Task 1 inline verify: `ArbSignal` and `EVSignal` instantiate with `game_time=None` default — PASSED
- Task 2 inline verify: Both embed builders show "Game Date" when `game_time` set, no field when `None` — PASSED
- Constraint test suite: `pytest services/test_arb_detector.py utils/test_odds_math.py -x -q` — 42 passed

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- models/signals.py: FOUND — `game_time: Optional[datetime] = None` on both models
- services/arb_detector.py: FOUND — `game_time=records[0].start_time` and `game_time=rec.start_time`
- utils/formatters.py: FOUND — `Game Date` conditional blocks in both embed builders
- Commits: FOUND — 29b4139, fd7ff4a
