# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## arb-math-fix — arbitrage scanner wrong arb %, wrong profit, false arb from mismatched spread lines
- **Date:** 2026-03-31
- **Error patterns:** arb_pct, sum_implied, equal-profit, spread, line_value, profit formula, phantom arb, false arbitrage, spreads, line mismatch, detect_arb
- **Root cause:** Two bugs in services/arb_detector.py detect_arb(). (1) arb_pct used (1 - sum_implied) * 100 instead of (1 - sum_implied) / sum_implied * 100, causing profit to be understated by a factor of sum_implied. (2) No line_value parity check: for spreads/totals, the code picked the best odds per team regardless of what point value the spread was at, allowing phantom arb from mismatched lines (e.g., TeamA -2.5 and TeamB -2.5 paired together).
- **Fix:** (1) Changed arb_pct formula to (1 - sum_implied) / sum_implied * 100. (2) Added abs(line_value) sub-grouping and an lv_a + lv_b ≈ 0 parity check before accepting a spread/totals arb. (3) Added /scan_arbs optional market_type filter.
- **Files changed:** services/arb_detector.py, services/test_arb_detector.py, cogs/arb.py
---
