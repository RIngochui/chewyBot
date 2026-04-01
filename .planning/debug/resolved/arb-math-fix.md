---
status: resolved
trigger: "arb-math-fix — arbitrage scanner broken math, wrong arb %, wrong profit, no spread line matching"
created: 2026-03-31T00:00:00Z
updated: 2026-03-31T01:00:00Z
---

## Current Focus

hypothesis: CONFIRMED — all math bugs fixed and market_type filter feature added to /scan_arbs.
test: Ran full test suite (84 tests)
expecting: All pass
next_action: Human verify, then archive
  (1) Wrong arb_pct and profit formula: uses (1-sum_implied) but equal-profit math requires (1-sum_implied)/sum_implied
  (2) No line_value (spread point) parity check — can falsely pair same-side spread bets
test: Applying fixes to arb_detector.py and updating test suite
expecting: After fix, Colorado 1.95/Vancouver 2.42/S=50 → profit≈$4.00, arb≈8%; spread line mismatch rejected
next_action: Apply fixes and add regression tests

## Symptoms

expected: |
  Given two-leg arb with total stake S=50, decimal odds o1=1.95, o2=2.42:
  - s1 = S / (1 + o1/o2) → correct equal-profit stakes
  - profit1 = s1 * o1 - S ≈ 4.00
  - profit2 = s2 * o2 - S ≈ 4.00
  - arb_percent = est_profit / S * 100 ≈ 8%
  Also: American odds must be converted to decimal before calculation.
  Also: spread/point value must match between the two legs.

actual: |
  Example 1 (BROKEN): Anaheim -2.5 @ DK 3.150, San Jose -2.5 @ BetMGM 3.000
  - Reports arb 34.92%, profit $17.46 on $50 stake
  - 1/3.15 + 1/3.00 = 0.650 — BOTH TEAMS ARE FAVORITES? Matching same-side bets.

  Example 2 (SLIGHTLY OFF): Colorado 1.950, Vancouver 2.420, stake $50
  - Reports 7.40% / $3.70 but correct answer is ~8% / ~$4.00.

errors: No Python exceptions — wrong results silently returned.

reproduction: Run the arb scanner or look at calculate_arbitrage / find_arb in the codebase.

started: Present in current codebase; never worked correctly for spreads.

## Eliminated

- hypothesis: Hardcoded $50 stake somewhere
  evidence: config.py has BANKROLL=100.0 default; detect_arb takes bankroll as a parameter from cog._bankroll; no hardcoded $50 found anywhere
  timestamp: 2026-03-31T00:04:00Z

- hypothesis: American odds being passed raw (not converted) into calculations
  evidence: adapters/odds_api.py explicitly requests oddsFormat=decimal; normalizer reads outcome["price"] directly as decimal_odds; american_to_decimal() is defined but not used in the pipeline (decimal format from API means no conversion needed)
  timestamp: 2026-03-31T00:05:00Z

## Evidence

- timestamp: 2026-03-31T00:01:00Z
  checked: services/arb_detector.py detect_arb() — stake and profit calculation
  found: |
    Line 59: stake_a = round(bankroll * (1.0 / odds_a) / sum_implied, 2)
    Line 60: stake_b = round(bankroll * (1.0 / odds_b) / sum_implied, 2)
    Line 61: profit = round(bankroll * arb_pct / 100, 2)
    The stake formula IS correct (equal-profit allocation via weighted implied probs).
    The profit formula IS also correct: profit = bankroll * (1 - sum_implied) = bankroll * arb_pct/100.
    For Colorado 1.95 / Vancouver 2.42 / S=50:
      sum_implied = 1/1.95 + 1/2.42 = 0.51282 + 0.41322 = 0.92604
      arb_pct = (1 - 0.92604) * 100 = 7.396%
      profit = 50 * 7.396/100 = 3.698 ≈ $3.70
    BUT expected is ~8% / ~$4.00.
  implication: |
    The reported 7.40% / $3.70 IS what the current code computes. The "correct" 8% / $4.00
    from the fix_spec uses the equal-profit definition:
      s1 = S * p1 / (p1+p2) = 50 * 0.51282 / 0.92604 = 27.68
      profit1 = s1 * o1 - S = 27.68 * 1.95 - 50 = 53.98 - 50 = 3.98 ≈ $4.00
    These are the SAME calculation. The issue is the definition of arb_pct:
    Current formula: arb_pct = (1 - sum_implied) * 100  → 7.40%
    Spec formula: arb_pct = est_profit / S * 100 → using equal-profit calc → ~8.0%
    The discrepancy comes from how arb_pct is defined vs estimated_profit is computed.
    With equal-profit stakes, profit = s1 * o1 - S = S*(p1/(p1+p2))*o1 - S = S*(p1*o1/(p1+p2) - 1)
    p1*o1 = (1/o1)*o1 = 1, so profit = S*(1/(p1+p2) - 1) = S*(1-sum_implied)/sum_implied
    = 50 * 0.07396 / 0.92604 = 50 * 0.07987 ≈ 3.99 ≈ $4.00
    Current code: profit = bankroll * arb_pct/100 = 50 * 0.0740 = $3.70 (WRONG)
    Correct formula: profit = bankroll * (1-sum_implied) / sum_implied

- timestamp: 2026-03-31T00:02:00Z
  checked: services/arb_detector.py — grouping and selection matching for spreads
  found: |
    Lines 36-46: Groups by (event_id, market_type), then finds best odds per selection_name.
    selection_name comes from odds_normalizer.py line 83: outcome["name"].
    For spreads, The Odds API uses the TEAM NAME as outcome["name"] (e.g., "Anaheim Ducks").
    So for a spreads market, there are exactly 2 selections: home team and away team.
    "Anaheim Ducks -2.5" and "San Jose Sharks +2.5" would both have selection_name=team name.
    If DraftKings has Anaheim -2.5 @ 3.150 and BetMGM has San Jose -2.5 @ 3.000...
    wait, that's San Jose at -2.5 on both, which means SAME side if Anaheim is -2.5 and SJ is -2.5.
    But more critically: The Odds API returns team names as outcome names for spreads.
    Two opposite spread sides would be: Anaheim Ducks (at -2.5) vs San Jose Sharks (at +2.5).
    These have DIFFERENT selection_names (different teams) — so grouping by selection_name IS correct
    for a two-outcome spread market.
    The bug in Example 1: "Anaheim -2.5 @ DK 3.150, San Jose -2.5 @ BetMGM 3.000" — 
    the -2.5 notation for BOTH means the odds data has BOTH teams at the same spread direction,
    which is physically impossible in a real spread market. This would only happen if the
    normalizer does NOT store the point value in selection_name (it doesn't — only in line_value).
  implication: |
    The grouping uses selection_name (team name). For spreads, two outcomes in the same market
    have different team names. Code correctly pairs TeamA vs TeamB.
    BUT: it does NOT validate that the line_value (spread point) matches between books.
    Book A: Anaheim -2.5 @ 3.150 | Book B: Anaheim +2.5 @ ... — these are different lines.
    Best Anaheim across books could be at -2.5 on one book and +2.5 at another — totally different bets.
    The "best" dict picks max odds for a given selection_name regardless of line_value.
    Example 1 explains: Anaheim at DK 3.150 (at some point) and San Jose at BetMGM 3.000 (different point).
    sum_implied = 1/3.15 + 1/3.00 = 0.650 < 1.0 → falsely detected as arb. Happens because both
    are strong "favorites" on their respective sides (mismatched lines create phantom arb).

- timestamp: 2026-03-31T00:03:00Z
  checked: services/arb_detector.py — spread line matching
  found: |
    No line_value validation exists anywhere in detect_arb().
    The best dict (line 37) only keys on selection_name, completely ignoring line_value.
    For spreads, best picks the highest odds for each team regardless of what spread point
    that bet is at. A book could have Anaheim -2.5 @ 3.15, another has Anaheim +2.5 @ 1.05.
    The code would pick 3.15 as "best for Anaheim" and pair it with San Jose's best odds —
    but if San Jose's best is also on a -2.5 line (i.e., same side), the math produces fake arb.
  implication: For spreads (and totals), best must also filter to matching line_value between selections.

- timestamp: 2026-03-31T00:04:00Z
  checked: config.py and services/arb_detector.py for hardcoded stake
  found: |
    config.py: BANKROLL: float = 100.0 — default is $100, no hardcoded $50 found.
    arb_detector.py: bankroll is a parameter, comes from cog._bankroll which is config.BANKROLL.
    No hardcoded $50 anywhere in the codebase. The fix_spec example uses S=50 for illustration only.
  implication: No hardcoded stake bug — bankroll is already config-driven.

- timestamp: 2026-03-31T00:05:00Z
  checked: adapters/odds_api.py get_odds() for odds format
  found: |
    Line 134: "oddsFormat": "decimal" — API is called with decimal format explicitly.
    The normalizer reads outcome["price"] directly as decimal_odds.
    american_to_decimal() exists in odds_math.py but is NOT called anywhere in the pipeline
    (the API returns decimal natively). decimal_to_american() IS called to populate american_odds field.
  implication: No American odds conversion bug in the pipeline — already using decimal format.

- timestamp: 2026-03-31T00:06:00Z
  checked: estimated_profit formula — mathematical derivation
  found: |
    Current: profit = bankroll * arb_pct / 100
    where arb_pct = (1 - sum_implied) * 100
    so profit = bankroll * (1 - sum_implied)  [the "overround savings" formula]
    
    But equal-profit stakes give: profit = bankroll * (1 - sum_implied) / sum_implied
    
    For Colorado/Vancouver: 
      sum_implied = 0.92604
      Current formula: 50 * 0.07396 = $3.698 → $3.70 reported
      Correct formula: 50 * 0.07396 / 0.92604 = $3.99 → ~$4.00 expected
    
    The arb_pct is also affected: spec says arb_pct = est_profit / S * 100
      Correct: (3.99 / 50) * 100 = 7.98% ≈ 8%
      Current: 7.40% (based on 1-sum_implied, not equal-profit math)
    
    The fix: arb_pct should be (1 - sum_implied) / sum_implied * 100
    and profit should be bankroll * (1 - sum_implied) / sum_implied
  implication: TWO calculations need fixing: arb_pct formula and profit formula.

## Resolution

root_cause: |
  Two bugs in services/arb_detector.py detect_arb():
  
  BUG 1 — wrong arb_pct / profit formula (lines 50-61 before fix):
    Old: arb_pct = (1 - sum_implied) * 100
    Old: profit   = bankroll * arb_pct / 100  →  bankroll * (1 - sum_implied)
    Correct formula for equal-profit stake allocation:
      arb_pct = (1 - sum_implied) / sum_implied * 100
      profit   = bankroll * arb_pct / 100
    The old formula omits the /sum_implied denominator. For Colorado 1.95 / Vancouver 2.42 / S=50:
      Old:     arb_pct=7.40%, profit=$3.70
      Correct: arb_pct=7.99%, profit=$3.99 ≈ $4.00
  
  BUG 2 — no spread/totals line parity validation:
    detect_arb() picked the highest odds for each selection_name ignoring line_value.
    For spreads, a team can appear at different point values across books (e.g., -2.5 at
    DraftKings, +2.5 at BetMGM — these are opposite sides, not the same bet).
    The old code could accidentally pair TeamA's best odds at point -2.5 with TeamB's
    best odds also at point -2.5, which are both "favorite" bets on opposite teams —
    a physically impossible arb. The sum of implied probabilities of two large-underdog
    payouts (e.g., 3.15 + 3.00) is 0.65 < 1.0, triggering a false arb detection.
    Fix: group records by abs(line_value) first, then validate that the two best
    selections' line_values sum to ~0 (i.e., are equal-and-opposite).

fix: |
  Modified services/arb_detector.py detect_arb():
  1. Fixed arb_pct formula: (1 - sum_implied) / sum_implied * 100
  2. Added line_value grouping: for spreads/totals, records are sub-grouped by
     abs(line_value) so only same-absolute-value lines are compared across books.
  3. Added line_value parity check: after selecting best odds per selection,
     validates lv_a + lv_b ≈ 0 (equal-and-opposite) before accepting as arb.
  4. Also updated services/test_arb_detector.py:
     - Updated Lakers/Warriors expected arb_pct from ~10.1% to ~11.24%
     - Added 3 equal-profit math regression tests (TestArbMathEqualProfit)
     - Added 3 spread line matching tests (TestSpreadLineMismatch)

verification: |
  All 84 tests pass.
  Colorado 1.95 / Vancouver 2.42 / S=50: profit=$3.99, arb_pct=7.99% ✓
  Both legs return equal payout (equal-profit property confirmed) ✓
  Mismatched spread lines (Anaheim -2.5 @ DK, SJ -2.5 @ BetMGM) rejected ✓
  Matching spread lines (both books Anaheim -2.5 / SJ +2.5) detected ✓
  h2h markets unaffected ✓
  /scan_arbs now accepts optional market_type choice (h2h/spreads/totals):
    - No argument → scans all markets (original behavior preserved) ✓
    - With argument → filters API request and post-normalization records ✓
    - Response message shows which market scope was scanned ✓

files_changed:
  - services/arb_detector.py
  - services/test_arb_detector.py
  - cogs/arb.py
