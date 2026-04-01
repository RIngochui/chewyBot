---
phase: 03-arbitrage-scanner
verified: 2026-03-31T08:00:00Z
status: gaps_found
score: 20/22 requirements verified
re_verification: true
gaps:
  - truth: "/status shows bankroll, min_arb_pct, min_ev_pct, enabled_sports, last scan time, quota remaining, and scanner running status"
    status: partial
    reason: "The /status embed contains 6 fields (Bankroll, Min Arb %, Min EV %, Enabled Sports, Last Scan, API Quota Remaining) but is missing the 7th field 'Scanner Running'. The plan spec line 411 required this field. Since auto_scan was removed (ARB-12 deviation), the implementation omitted the field entirely rather than replacing it with a static 'N/A — on-demand mode' value."
    artifacts:
      - path: "cogs/arb.py"
        issue: "status command embed has 6 add_field calls; 'Scanner Running' field absent (plan spec lines 398-413 require it as 7th field)"
    missing:
      - "Add 'Scanner Running' field to /status embed with static value 'N/A — on-demand mode' to reflect the accepted ARB-12 deviation"

human_verification:
  - test: "Run /scan_arbs in Discord with MOCK_MODE=True"
    expected: "Bot replies 'Scan complete. Found 2 arb(s) and 3 +EV opportunity(ies).' ARB_CHANNEL_ID receives two arb embeds titled '⚡ Possible Arbitrage — chewyBot' and three EV embeds titled '📈 +EV Opportunity — chewyBot'. No 'guaranteed' language visible. Footer reads 'Not financial advice. Results are estimated and may not be realised.'"
    why_human: "Requires running Discord bot and inspecting channel output programmatically — cannot verify channel.send() delivery without live bot"
  - test: "Run /status in Discord"
    expected: "Embed shows 7 fields including 'Scanner Running'. Currently shows 6 fields — gap still open until Scanner Running field is added."
    why_human: "Requires running bot and visual inspection of embed field count"
  - test: "Run /set_bankroll 500, restart bot, run /status"
    expected: "Bankroll still shows $500.00 — config loaded from bot_config table on startup"
    why_human: "Requires verifying startup config load from DB; cogs/arb.py does not show load-on-start logic in __init__"
---

# Phase 03: Arbitrage Scanner Verification Report

**Phase Goal:** The odds scanner fetches live (or mock) data, detects arb and +EV opportunities above configured thresholds, auto-scans every SCAN_INTERVAL_SECONDS, and posts formatted alerts to ARB_CHANNEL_ID

**Verified:** 2026-03-31T08:00:00Z

**Status:** gaps_found (1 minor gap remaining)

**Re-verification:** Yes — after gap closure

---

## Re-verification Summary

**Previous status:** gaps_found (14/22 verified, 5 gaps across 6 items)

**Gaps closed (5 of 6):**
- CLOSED: SUPPORTED_BOOKS regression — restored to `['fanduel', 'draftkings', 'betmgm', 'bet365', 'espnbet']`; all 4 required books present
- CLOSED: Mock pipeline produces 0 arb signals — fixed by SUPPORTED_BOOKS restoration; pipeline now produces 2 arb + 3 EV signals
- CLOSED: ARB-03 test fails — `test_class_attributes_preserved` now passes; 78/78 tests pass
- CLOSED: REQUIREMENTS.md ARB-08/09/10 marked Pending — all now `[x]` and `Complete` in traceability table
- ACCEPTED: ARB-12 auto-scan loop — human-approved deviation (on-demand /scan_arbs replaces auto-polling)

**Gaps remaining (1 of 6):**
- PARTIAL: /status "Scanner Running" field still absent from embed

**Regressions:** None — all 17 previously-verified truths still pass.

**Score improvement:** 14/22 → 20/22 (goal truths verified)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `american_to_decimal(+150)` returns 2.5, `-110` returns ~1.909 | VERIFIED | utils/odds_math.py line 14-17; spot-check confirmed |
| 2 | `implied_probability(2.5)` returns 0.4 | VERIFIED | utils/odds_math.py line 41; spot-check confirmed |
| 3 | `no_vig_probability([2.5, 1.75])` returns two fair probs summing to 1.0 | VERIFIED | utils/odds_math.py line 50-52; sum=1.0 confirmed |
| 4 | `build_arb_embed(ArbSignal)` returns embed with "Possible Arbitrage" title and disclaimer footer | VERIFIED | utils/formatters.py line 17; title "⚡ Possible Arbitrage — chewyBot", footer "Not financial advice..." |
| 5 | `build_ev_embed(EVSignal)` returns embed with "+EV Opportunity" title and disclaimer footer | VERIFIED | utils/formatters.py line 68; title "📈 +EV Opportunity — chewyBot" confirmed |
| 6 | Mock mode returns events from `mock/odds_api_sample.json` fresh on every call | VERIFIED | adapters/odds_api.py line 124-127; 18 adapter tests pass |
| 7 | Live mode calls API with exponential backoff (3 retries) and returns [] on failure | VERIFIED | adapters/odds_api.py `_fetch_with_retry`; backoff tests pass |
| 8 | `_quota_remaining` updated from `x-requests-remaining` after live success | VERIFIED | adapters/odds_api.py line 142-147; test confirms |
| 9 | `normalize()` produces one NormalizedOdds per (bookmaker, market, outcome) | VERIFIED | services/odds_normalizer.py; 24 tests pass |
| 10 | `event_id` slugified as `home_away_YYYYMMDD`; `market_key` as `event_id_market_selection` | VERIFIED | services/odds_normalizer.py line 53, 70; confirmed |
| 11 | `detect_arb()` finds arb when `sum(1/best_odds) < 1.0`; computes stakes and profit | VERIFIED | services/arb_detector.py; 17 tests pass |
| 12 | `detect_ev()` finds outcomes where `ev_pct >= min_ev_pct` | VERIFIED | services/arb_detector.py; tests pass |
| 13 | SQL constants for INSERT and SELECT arb/EV signals exist in queries.py | VERIFIED | database/queries.py; all five constants importable |
| 14 | `/scan_arbs` triggers _run_scan and reports found counts in ephemeral reply | VERIFIED | cogs/arb.py line 144-156; full wiring confirmed |
| 15 | `/latest_arbs` and `/latest_ev` return last 5 signals as embeds from DB | VERIFIED | cogs/arb.py lines 158-211; both commands wired to SELECT queries |
| 16 | `/set_bankroll`, `/set_min_arb`, `/set_min_ev` update runtime config and persist to bot_config | VERIFIED | cogs/arb.py lines 213-247; UPDATE_BOT_CONFIG wired |
| 17 | `/toggle_sport` enables/disables sport and persists to bot_config | VERIFIED | cogs/arb.py lines 249-264; UPDATE_BOT_CONFIG wired |
| 18 | Auto-scanner loop starts in cog_load and fires every SCAN_INTERVAL_SECONDS | ACCEPTED DEVIATION | No tasks.loop, no cog_load, no auto_scan — intentional (ARB-12, human-approved). Replaced by on-demand /scan_arbs. |
| 19 | Same market_key not re-alerted unless arb_pct improves >0.2% | VERIFIED | Dedup code in _run_scan (_seen dict, >0.2 check) verified; pipeline now produces 2 arb signals — dedup path fully exercisable |
| 20 | /status shows all fields including scanner running status | PARTIAL | 6 of 7 plan-spec fields present; "Scanner Running" field absent from embed |
| 21 | With MOCK_MODE=True, /scan_arbs posts arb embed(s) to ARB_CHANNEL_ID | VERIFIED (code path) | End-to-end pipeline confirmed: 2 arb signals + 3 EV signals produced from mock data with fixed SUPPORTED_BOOKS; embeds built correctly; channel.send() wired — delivery requires human verification in live Discord |
| 22 | ARB-03: Books covered — fanduel, draftkings, betmgm, bet365 | VERIFIED | SUPPORTED_BOOKS = ['fanduel', 'draftkings', 'betmgm', 'bet365', 'espnbet']; all 4 required books present; test_class_attributes_preserved PASSES |

**Score: 20/22 truths verified (1 partial, 1 accepted deviation)**

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `utils/odds_math.py` | Four math helpers: american_to_decimal, decimal_to_american, implied_probability, no_vig_probability | VERIFIED | All four functions; 19 tests pass |
| `utils/formatters.py` | build_arb_embed, build_ev_embed | VERIFIED | Both functions; titles and footers correct; no "guaranteed" language |
| `utils/test_odds_math.py` | 19 pytest tests | VERIFIED | 19 tests, all pass |
| `adapters/odds_api.py` | OddsApiAdapter with get_sports, get_events, get_odds, get_quota_remaining, close | VERIFIED | All methods; SUPPORTED_BOOKS now includes all 4 required books + espnbet |
| `adapters/test_odds_api.py` | 18 async tests | VERIFIED | 18/18 pass — test_class_attributes_preserved now passes |
| `services/odds_normalizer.py` | normalize() with ARB-07 keys | VERIFIED | 24 tests pass |
| `services/test_odds_normalizer.py` | 24 tests | VERIFIED | All 24 pass |
| `services/arb_detector.py` | detect_arb() and detect_ev() | VERIFIED | Both functions; 17 tests pass |
| `services/test_arb_detector.py` | 17 tests | VERIFIED | All 17 pass |
| `database/queries.py` | INSERT_ARB_SIGNAL, INSERT_EV_SIGNAL, SELECT_LATEST_ARB_SIGNALS, SELECT_LATEST_EV_SIGNALS, UPDATE_BOT_CONFIG | VERIFIED | All five constants present and importable |
| `mock/odds_api_sample.json` | 5 events across NBA/NFL/NHL with multiple bookmakers | VERIFIED | 5 events present; fanduel, draftkings, betmgm, bet365 data; produces 2 arb + 3 EV signals |
| `cogs/arb.py` | ArbCog with 9 slash commands, dedup, signal persistence | PARTIAL | 9 commands present; tasks.loop/auto_scan/cog_load absent (accepted ARB-12 deviation); "Scanner Running" embed field absent from /status |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `utils/odds_math.py` | `services/arb_detector.py` | `from utils.odds_math import no_vig_probability` | VERIFIED | arb_detector.py line 8 |
| `utils/formatters.py` | `cogs/arb.py` | `from utils.formatters import build_arb_embed, build_ev_embed` | VERIFIED | arb.py line 37; called in _run_scan lines 121, 127 |
| `adapters/odds_api.py` | `mock/odds_api_sample.json` | `json.load` in mock mode | VERIFIED | odds_api.py line 125-127 |
| `adapters/odds_api.py` | `api.the-odds-api.com/v4` | `httpx.AsyncClient.get` via `_fetch_with_retry` | VERIFIED | odds_api.py line 57 |
| `services/odds_normalizer.py` | `utils/odds_math.py` | `from utils.odds_math import decimal_to_american` | VERIFIED | odds_normalizer.py line 10 |
| `services/odds_normalizer.py` | `models/odds.py` | `NormalizedOdds(` | VERIFIED | odds_normalizer.py line 73 |
| `services/arb_detector.py` | `models/signals.py` | `ArbSignal(`, `EVSignal(` | VERIFIED | arb_detector.py lines 63, 149 |
| `cogs/arb.py` | `adapters/odds_api.py` | `self.adapter.get_odds()` in `_run_scan` | VERIFIED | arb.py line 80 |
| `cogs/arb.py` | `services/odds_normalizer.py` | `await normalize(` | VERIFIED | arb.py line 86 |
| `cogs/arb.py` | `services/arb_detector.py` | `await detect_arb(`, `await detect_ev(` | VERIFIED | arb.py lines 94-95 |
| `cogs/arb.py` | `database/queries.py` | `INSERT_ARB_SIGNAL`, `SELECT_LATEST_ARB_SIGNALS` | VERIFIED | arb.py lines 27-33, 102, 163 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cogs/arb.py` `_run_scan` | `arb_signals` | `detect_arb(all_normalized, ...)` after normalize from OddsApiAdapter | YES — 2 arb signals in mock mode with corrected SUPPORTED_BOOKS | VERIFIED |
| `cogs/arb.py` `_run_scan` | `ev_signals` | `detect_ev(...)` guarded by `config.ENABLE_EV_SCAN` | YES — 3 EV signals produced; guarded by ENABLE_EV_SCAN env var (default False) | FLOWING (conditional) |
| `cogs/arb.py` `latest_arbs` | `rows` | `SELECT_LATEST_ARB_SIGNALS` from SQLite `arb_signals` table | YES — real DB query | VERIFIED |
| `utils/formatters.py` | embed fields | `ArbSignal`/`EVSignal` model fields | YES — reads signal attributes | VERIFIED |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| odds_math functions return correct values | `american_to_decimal(150)` | 2.5 | PASS |
| `american_to_decimal(-110)` | `american_to_decimal(-110)` | 1.909 | PASS |
| `no_vig_probability` sums to 1.0 | `sum(no_vig_probability([2.5, 1.75]))` | 1.0 | PASS |
| End-to-end pipeline finds arb signals | normalize + detect_arb on mock data with fixed SUPPORTED_BOOKS | 2 arb signals (10.10% NBA Lakers vs Warriors fanduel/draftkings, 1.10% NHL Bruins vs Leafs fanduel/betmgm) | PASS |
| End-to-end pipeline finds EV signals | normalize + detect_ev on mock data | 3 EV signals | PASS |
| Dedup path exercisable | 2 arb signals pass _seen check; 2 would post to channel | 2 signals pass (first-run, no prior _seen entries) | PASS |
| All phase test suites pass | `python3 -m pytest utils/ services/ adapters/` | 78 passed in 0.17s | PASS |
| embed footer has no "guaranteed" | `grep "guaranteed" cogs/arb.py utils/formatters.py` | No occurrences | PASS |
| cogs/arb.py syntax valid | `ast.parse` via import | OK | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ARB-01 | 03-02 | Adapter pattern — adapters/base.py abstract interface | SATISFIED | adapters/odds_api.py implements SportsbookAdapter ABC |
| ARB-02 | 03-02 | adapters/odds_api.py uses The Odds API; reads ODDS_API_KEY | SATISFIED | odds_api.py BASE_URL and api_key param |
| ARB-03 | 03-02 | Books: fanduel, draftkings, betmgm, bet365 | SATISFIED | SUPPORTED_BOOKS = ['fanduel', 'draftkings', 'betmgm', 'bet365', 'espnbet']; test passes |
| ARB-04 | 03-02 | MOCK_MODE=true loads from mock/odds_api_sample.json | SATISFIED | odds_api.py line 124-127 |
| ARB-05 | 03-02 | Quota remaining tracked from response headers, exposed in /status | SATISFIED | odds_api.py line 142-147; /status shows quota |
| ARB-06 | 03-03 | Canonical schema: sport, league, event_name, ..., event_id, market_key | SATISFIED | NormalizedOdds model fully populated by normalize() |
| ARB-07 | 03-03 | event_id slugified; market_key format | SATISFIED | odds_normalizer.py lines 53, 70 |
| ARB-08 | 03-04 | Arb detection: sum(1/best_odds) < 1.0; calculates arb_pct, stakes, profit | SATISFIED | arb_detector.py detect_arb(); REQUIREMENTS.md now [x] |
| ARB-09 | 03-04 | MIN_ARB_PCT threshold; dedup skips re-alerting unless >0.2% improvement | SATISFIED | Code + runtime verified: 2 arb signals exercised; dedup logic confirmed |
| ARB-10 | 03-04 | +EV detection via no_vig_probability; MIN_EV_PCT threshold | SATISFIED | detect_ev() correct; 3 EV signals produced; REQUIREMENTS.md now [x] |
| ARB-11 | 03-01 | Math helpers in utils/odds_math.py | SATISFIED | All four functions; 19 tests pass |
| ARB-12 | 03-05 | Auto-scanner loop every SCAN_INTERVAL_SECONDS, posts to ARB_CHANNEL_ID | ACCEPTED DEVIATION | No tasks.loop; replaced by on-demand /scan_arbs — human-approved deviation; REQUIREMENTS.md updated accordingly |
| ARB-13 | 03-05 | /ping — bot latency | SATISFIED | arb.py line 136 |
| ARB-14 | 03-05 | /scan — trigger manual scan (renamed /scan_arbs) | SATISFIED | Implemented as /scan_arbs; functionally identical |
| ARB-15 | 03-05 | /latest_arbs — last 5 arb alerts as embeds | SATISFIED | arb.py lines 158-186; DB query wired |
| ARB-16 | 03-05 | /latest_ev — last 5 EV alerts as embeds | SATISFIED | arb.py lines 188-211; DB query wired |
| ARB-17 | 03-05 | /set_bankroll, /set_min_arb, /set_min_ev — update runtime config | SATISFIED | arb.py lines 213-247; persist to bot_config |
| ARB-18 | 03-05 | /toggle_sport — enable/disable sport | SATISFIED | arb.py lines 249-264 |
| ARB-19 | 03-05 | /status — config, last scan time, quota remaining | PARTIAL | 6 of 7 plan-spec fields; missing "Scanner Running" field |
| ARB-20 | 03-01 | Arb embed title "⚡ Possible Arbitrage — chewyBot" | SATISFIED | formatters.py; confirmed by spot-check |
| ARB-21 | 03-01 | EV embed title "📈 +EV Opportunity — chewyBot" | SATISFIED | formatters.py line 68 |
| ARB-22 | 03-01 | Footers never say "guaranteed" | SATISFIED | Footer: "...may not be realised"; no "guaranteed" anywhere |

**Requirements summary:**
- 20 SATISFIED
- 1 ACCEPTED DEVIATION (ARB-12, human-approved)
- 1 PARTIAL (ARB-19: /status missing "Scanner Running" field)

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `cogs/arb.py` | 95 | `if config.ENABLE_EV_SCAN else []` guards detect_ev() | WARNING | `ENABLE_EV_SCAN` defaults to `False` — EV signals silently disabled unless operator sets the env var. Not a bug; operational awareness item. |
| `cogs/arb.py` | 144 | Command name is `scan_arbs` not `scan` | INFO | Accepted deviation from plan spec; /scan does not exist; /scan_arbs is the correct invocation |
| `cogs/arb.py` | 266-290 | `/status` embed missing "Scanner Running" field | WARNING | Plan spec line 411 required this field; implementation omits it entirely rather than substituting a static "N/A — on-demand mode" value |

No blockers. No "guaranteed" language. No TODO/FIXME/PLACEHOLDER patterns in phase files.

---

## Human Verification Required

### 1. End-to-End Discord Scan

**Test:** With MOCK_MODE=True set in `.env`, run `/scan_arbs` in Discord.
**Expected:** Bot replies "Scan complete. Found 2 arb(s) and 3 +EV opportunity(ies)." ARB_CHANNEL_ID receives two arb embeds titled "⚡ Possible Arbitrage — chewyBot" and three EV embeds titled "📈 +EV Opportunity — chewyBot" (EV only when ENABLE_EV_SCAN=True). Footer reads "Not financial advice. Results are estimated and may not be realised." No "guaranteed" language visible.
**Why human:** Requires running Discord bot and inspecting channel delivery — channel.send() cannot be verified programmatically without live bot.

### 2. /status Command Field Count

**Test:** Run `/status` in Discord.
**Expected:** Embed shows 7 fields. Currently shows 6 — "Scanner Running" is absent. Confirm whether the missing field is acceptable or requires adding a static "N/A — on-demand mode" value.
**Why human:** Design decision on whether the partial gap is acceptable, plus visual inspection of embed.

### 3. Config Persistence Across Restart

**Test:** Run `/set_bankroll 500`, stop and restart the bot, run `/status`.
**Expected:** Bankroll still shows $500.00 — loaded from bot_config table on startup.
**Why human:** `cogs/arb.py __init__` initializes from `config.BANKROLL` (env default), not from the bot_config DB table. The `/set_*` commands write to DB but on-restart the value would revert to the env default unless a load-from-DB step exists elsewhere in the startup path. This needs runtime confirmation.

---

## Gaps Summary

One gap remains from the original six:

**Remaining gap — /status "Scanner Running" field (minor):** The plan spec for `/status` (03-05-PLAN.md line 411) included a "Scanner Running" field showing `self.auto_scan.is_running()`. When the auto-scan loop was removed (ARB-12 accepted deviation), the field was dropped entirely rather than replaced with a static "N/A — on-demand mode" value. ARB-19 per REQUIREMENTS.md is now marked `[x]` because the requirement description ("current config, last scan time, Odds API quota remaining") is fully met. The gap is against the plan spec's 7-field embed, not against the requirement text. Low severity — does not prevent any core scanning functionality.

All other gaps from the initial verification are closed. The core value of Phase 3 is functioning: SUPPORTED_BOOKS is corrected, the end-to-end pipeline detects 2 arb and 3 EV signals from mock data, all 78 tests pass, and REQUIREMENTS.md accurately reflects completion status.

---

_Verified: 2026-03-31_
_Re-verification: Yes — after gap closure_
_Verifier: Claude (gsd-verifier)_
