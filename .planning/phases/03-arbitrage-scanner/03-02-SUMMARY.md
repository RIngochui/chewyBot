---
phase: 03-arbitrage-scanner
plan: 02
subsystem: api
tags: [httpx, odds-api, mock-mode, exponential-backoff, async, tdd, pytest-asyncio]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "adapters/base.py SportsbookAdapter ABC interface + OddsApiAdapter stub"
provides:
  - "OddsApiAdapter fully implemented in adapters/odds_api.py"
  - "Mock mode: json.load from mock/odds_api_sample.json, reloaded each call"
  - "Live mode: httpx.AsyncClient with 3-retry exponential backoff (1s, 2s)"
  - "Quota tracking from x-requests-remaining response header"
  - "Graceful failure: returns [] after 3 retries, never raises on network error"
  - "18 passing tests in adapters/test_odds_api.py covering all behaviors"
affects:
  - "03-arbitrage-scanner plan 03 (odds normalizer consumes OddsApiAdapter output)"
  - "03-arbitrage-scanner plan 04 (arb/EV detector uses normalized output)"
  - "03-arbitrage-scanner plan 05 (cogs/arb.py wires OddsApiAdapter into scan loop)"

# Tech tracking
tech-stack:
  added: [httpx==0.28.1, pytest-asyncio==1.2.0, pytest-mock==3.15.1]
  patterns:
    - "Persistent httpx.AsyncClient in __init__ — reuses TCP connections across scan loop"
    - "Private _fetch_with_retry method handles all retry logic; callers only check None"
    - "Mock mode: open(Path('mock/...')) on each call, no caching — catches dev file edits"
    - "TDD cycle: RED commit (test file) then GREEN commit (implementation + fixed tests)"

key-files:
  created:
    - "adapters/test_odds_api.py — 18 async tests covering mock mode, live mode, backoff, quota"
  modified:
    - "adapters/odds_api.py — full implementation replacing Phase 1 NotImplementedError stubs"

key-decisions:
  - "Persistent httpx.AsyncClient in __init__ (not created per-request) — reuses TCP connections across the scan loop"
  - "asyncio.sleep(2**attempt) giving 1s then 2s (not 1s/2s/4s): 2^0=1, 2^1=2, attempt 2 logs warning and returns None without sleeping"
  - "Mock mode returns all events from file regardless of sport_key filter — simpler, consistent with mock intent"
  - "TDD: wrote test file first with patch.object capturing mock before context exit — avoids AttributeError after with-block"

patterns-established:
  - "Private _fetch_with_retry returns Optional[httpx.Response]; callers check None to detect failure"
  - "Quota update uses int() cast with ValueError guard — header may be absent or malformed"

requirements-completed: [ARB-01, ARB-02, ARB-03, ARB-04, ARB-05]

# Metrics
duration: 8min
completed: 2026-03-31
---

# Phase 03 Plan 02: OddsApiAdapter Summary

**httpx-based OddsApiAdapter with mock file loading, live API calls, 3-retry exponential backoff, and response-header quota tracking**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-31T05:04:56Z
- **Completed:** 2026-03-31T05:11:29Z
- **Tasks:** 1 (TDD: RED + GREEN + test fix)
- **Files modified:** 2

## Accomplishments

- Replaced Phase 1 NotImplementedError stubs with full OddsApiAdapter implementation
- Mock mode reads `mock/odds_api_sample.json` fresh on every `get_odds()` call — file edits picked up without restart
- Live mode uses persistent `httpx.AsyncClient` with `_fetch_with_retry`: 3 attempts, `asyncio.sleep(1s, 2s)` backoff
- `_quota_remaining` updated from `x-requests-remaining` header after every live success
- Network failure after 3 retries returns `[]` and logs a warning — never raises
- 18 tests covering all spec behaviors, all passing

## Task Commits

Each task committed atomically (TDD 3-commit pattern):

1. **Task 1 RED: Failing tests** - `3abcad4` (test)
2. **Task 1 GREEN: Implementation + test fixes** - `ceb3197` (feat)

**Plan metadata:** (docs commit below)

_TDD task: RED commit for tests, GREEN commit for implementation + test mock capture fix_

## Files Created/Modified

- `/Users/ringochui/Projects/chewyBot/adapters/odds_api.py` — full implementation: `_fetch_with_retry`, `get_sports`, `get_events`, `get_odds`, `get_quota_remaining`, `close()`
- `/Users/ringochui/Projects/chewyBot/adapters/test_odds_api.py` — 18 pytest-asyncio tests for mock/live/backoff/quota/lifecycle

## Decisions Made

- **Persistent client:** `httpx.AsyncClient(timeout=10.0)` created in `__init__` — reuses TCP connections; disposable via `close()` for clean shutdown
- **Backoff sleep durations:** `asyncio.sleep(2**attempt)` gives 1s after attempt 0, 2s after attempt 1; attempt 2 logs warning and returns None without additional sleep
- **Mock filter:** Mock mode returns all events from file regardless of `sport_key` argument — correct for dev/test use where file represents one complete snapshot
- **Test mock capture:** Captured mock object before `with patch.object` context instead of re-accessing attribute after context exits

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertions after patch.object context exit**
- **Found during:** Task 1 GREEN (running tests, 5 failures)
- **Issue:** Tests using `live_adapter._client.get.call_args` after the `with patch.object(...)` block exits — attribute reverts to the original function (no `call_args`)
- **Fix:** Captured the `AsyncMock` before the `with` block: `get_mock = AsyncMock(...); with patch.object(..., new=get_mock):` then asserted on `get_mock.call_args`
- **Files modified:** `adapters/test_odds_api.py`
- **Verification:** 18/18 tests pass after fix
- **Committed in:** `ceb3197` (combined with GREEN implementation)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test assertions)
**Impact on plan:** Fix was internal to tests only. Implementation unchanged. No scope creep.

## Issues Encountered

- `httpx` and `pytest-asyncio` not installed in system Python 3.9 (macOS Xcode Python). Installed via `pip install httpx pytest-asyncio pytest-mock` — packages added to user site-packages, all tests pass.

## Known Stubs

None — all methods fully implemented. `get_sports`, `get_events`, `get_odds`, `get_quota_remaining`, and `close()` are all complete.

## User Setup Required

None — no external service configuration required for this plan. ODDS_API_KEY is consumed at runtime from config.py.

## Next Phase Readiness

- `OddsApiAdapter` is the data source for the normalizer (plan 03) and arb/EV detector (plan 04)
- Mock mode is fully functional — all downstream plans can run with `MOCK_MODE=True` during development
- Live mode ready; requires `ODDS_API_KEY` from `.env` at runtime

## Self-Check: PASSED

- FOUND: adapters/odds_api.py
- FOUND: adapters/test_odds_api.py
- FOUND: 03-02-SUMMARY.md
- FOUND: commit 3abcad4 (RED tests)
- FOUND: commit ceb3197 (GREEN implementation)

---
*Phase: 03-arbitrage-scanner*
*Completed: 2026-03-31*
