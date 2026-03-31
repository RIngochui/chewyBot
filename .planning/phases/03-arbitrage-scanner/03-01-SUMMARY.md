---
phase: 03-arbitrage-scanner
plan: "01"
subsystem: utils
tags: [odds-math, formatters, embed-builders, pure-math, tdd]
dependency_graph:
  requires: []
  provides:
    - utils/odds_math.py (american_to_decimal, decimal_to_american, implied_probability, no_vig_probability)
    - utils/formatters.py (build_arb_embed, build_ev_embed)
  affects:
    - services/arb_detector.py (imports odds_math)
    - services/odds_normalizer.py (imports odds_math)
    - cogs/arb.py (imports formatters)
tech_stack:
  added: []
  patterns:
    - Pure-math functions with no side effects or imports
    - TDD red-green cycle for math helpers
    - discord.Embed construction pattern with EMBED_COLOR constant
key_files:
  created:
    - utils/test_odds_math.py
  modified:
    - utils/odds_math.py
    - utils/formatters.py
decisions:
  - Footer text uses "may not be realised" instead of "not guaranteed" — avoids "guaranteed" substring while meeting ARB-22 safety constraint; plan verification script checks for absence of the literal word
  - Docstring references to ARB-22 phrased as "no profit claims" rather than quoting the forbidden word
metrics:
  duration: "3m 51s"
  completed_date: "2026-03-31"
  tasks_completed: 2
  files_modified: 3
---

# Phase 03 Plan 01: Math Helpers and Embed Builders Summary

Pure-math odds conversion layer (4 helpers) and Discord embed presentation layer (2 builders) implemented with TDD; all stubs replaced, 19 tests passing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement utils/odds_math.py — four math helpers (TDD) | 6ed228c (tests), 1b95301 (impl) | utils/test_odds_math.py, utils/odds_math.py |
| 2 | Implement utils/formatters.py — arb and EV embed builders | 987e993 | utils/formatters.py |

## What Was Built

**utils/odds_math.py** — Four pure-math helpers:
- `american_to_decimal(american_odds: int) -> float` — positive: `(n/100)+1`, negative: `(100/|n|)+1`
- `decimal_to_american(decimal_odds: float) -> int` — `>=2.0`: `round((d-1)*100)`, `<2.0`: `round(-100/(d-1))`
- `implied_probability(decimal_odds: float) -> float` — `1/d`
- `no_vig_probability(odds_list: list[float]) -> list[float]` — normalise raw implied probs to sum to 1.0

**utils/test_odds_math.py** — 19 pytest test cases covering positive/negative odds, edge cases (evens, +100, -200), two/three/four-outcome no-vig scenarios.

**utils/formatters.py** — Two Discord embed builders:
- `build_arb_embed(signal: ArbSignal) -> discord.Embed` — title "⚡ Possible Arbitrage — chewyBot", 7 fields, disclaimer footer
- `build_ev_embed(signal: EVSignal) -> discord.Embed` — title "📈 +EV Opportunity — chewyBot", 8 fields, disclaimer footer
- `build_parlay_embed` — remains `NotImplementedError` stub for Phase 4

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Footer text adjusted to pass "guaranteed" substring check**
- **Found during:** Task 2 verification
- **Issue:** Plan specified footer "not guaranteed" but its own verification script (`assert 'guaranteed' not in e.footer.text.lower()`) treats any occurrence of the substring as a failure. The docstrings also contained the word.
- **Fix:** Footer text changed to "Not financial advice. Results are estimated and may not be realised." (conveys identical safety meaning). Docstrings rephrased from "never claims guaranteed profit" to "no profit claims" to keep the file clean.
- **Files modified:** utils/formatters.py
- **Commit:** 987e993

## Verification Results

```
19 passed in 0.01s   (utils/test_odds_math.py)
formatters imports OK
OK: no guaranteed language
```

## Known Stubs

- `build_parlay_embed` in utils/formatters.py — intentional Phase 4 stub; does not affect this plan's deliverables.

## Self-Check: PASSED

Files exist:
- utils/odds_math.py — FOUND
- utils/formatters.py — FOUND
- utils/test_odds_math.py — FOUND

Commits exist:
- 6ed228c — FOUND (TDD red: failing tests)
- 1b95301 — FOUND (TDD green: implementation)
- 987e993 — FOUND (formatters implementation)
