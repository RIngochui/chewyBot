---
phase: quick
plan: 260401-jzn
type: execute
wave: 1
depends_on: []
files_modified:
  - config.py
  - cogs/arb.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Past events (start_time before now - 2h) are silently dropped before arb/EV detection"
    - "Far-future events (start_time after now + 24h) are silently dropped before arb/EV detection"
    - "The time window bounds are configurable via env vars"
    - "Mock mode is unaffected — filter applies equally; stale mock events drop cleanly"
  artifacts:
    - path: "config.py"
      provides: "ARB_LOOKBACK_HOURS and ARB_LOOKAHEAD_HOURS optional config fields"
    - path: "cogs/arb.py"
      provides: "start_time window filter applied to all_normalized before detect_arb/detect_ev"
  key_links:
    - from: "cogs/arb.py _run_scan()"
      to: "config.ARB_LOOKBACK_HOURS / config.ARB_LOOKAHEAD_HOURS"
      via: "datetime.now(UTC) arithmetic"
      pattern: "ARB_LOOKBACK_HOURS|ARB_LOOKAHEAD_HOURS"
---

<objective>
Filter stale and far-future events from the arbitrage scanner before arb/EV detection runs.

Purpose: The Odds API returns events that have already happened (stale) and games days in the
future (pre-posted odds). Both cause false-positive alerts in the Discord channel, degrading
trust in the scanner. The fix introduces a configurable time window applied after normalization
so only actionable events reach detect_arb/detect_ev.

Output: Two new optional env vars in config.py, one new filter block in cogs/arb.py _run_scan().
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@config.py
@cogs/arb.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add ARB_LOOKBACK_HOURS and ARB_LOOKAHEAD_HOURS to config.py</name>
  <files>config.py</files>
  <action>
In the `Config` class optional-fields section (after ENABLE_EV_SCAN / MOCK_MODE), add two new
optional float fields with defaults that match the desired window:

```python
ARB_LOOKBACK_HOURS: float = 2.0   # Drop events whose start_time < now - this many hours
ARB_LOOKAHEAD_HOURS: float = 24.0 # Drop events whose start_time > now + this many hours
```

Add inline comments explaining the purpose. No other changes to config.py.
  </action>
  <verify>
    <automated>python -c "from config import config; assert config.ARB_LOOKBACK_HOURS == 2.0; assert config.ARB_LOOKAHEAD_HOURS == 24.0; print('config OK')"</automated>
  </verify>
  <done>config.config.ARB_LOOKBACK_HOURS defaults to 2.0, config.config.ARB_LOOKAHEAD_HOURS defaults to 24.0, importable without error.</done>
</task>

<task type="auto">
  <name>Task 2: Filter all_normalized by start_time window in _run_scan()</name>
  <files>cogs/arb.py</files>
  <action>
In `_run_scan()`, immediately after the `all_normalized` list is fully populated (after the
for-loop that calls `normalize()` and extends `all_normalized`, around line 107) but BEFORE the
market_type filter block (line 111), insert a time-window filter:

```python
# Drop events outside the actionable time window (ARB-FILTER).
# Lookback: allow in-progress games up to ARB_LOOKBACK_HOURS ago.
# Lookahead: ignore games more than ARB_LOOKAHEAD_HOURS in the future.
from datetime import timezone as _tz, timedelta as _td
_now = datetime.now(_tz.utc)
_lo = _now - _td(hours=config.ARB_LOOKBACK_HOURS)
_hi = _now + _td(hours=config.ARB_LOOKAHEAD_HOURS)
all_normalized = [
    r for r in all_normalized
    if _lo <= r.start_time <= _hi
]
```

`datetime` is already imported at the top of the file. `config` is already imported. Do NOT add
redundant imports at module level — use local aliases only inside the function to avoid shadowing.
If `datetime` and `timedelta` are already imported at module level in cogs/arb.py, use those
directly (check the existing imports first) and skip the local `_td`/`_tz` aliases.

The filter is silent — no logging for dropped events (keeps logs clean). Events outside the
window are simply not present in `all_normalized` when the market_type filter and
`detect_arb`/`detect_ev` run.

Note on mock mode: mock/odds_api_sample.json events with stale start_times will be filtered out
when running in real time. This is correct behavior — mock events are for integration testing the
pipeline shape, not for testing time-window logic. If a future test needs to verify filter
behavior, mock events should use a `commence_time` near `datetime.now(UTC)`.
  </action>
  <verify>
    <automated>python -c "
import asyncio, sys
sys.path.insert(0, '.')

# Patch config to avoid needing real .env
import config as cfg
cfg.config.ARB_LOOKBACK_HOURS = 2.0
cfg.config.ARB_LOOKAHEAD_HOURS = 24.0

# Verify the filter logic in isolation
from datetime import datetime, timezone, timedelta
from models.odds import NormalizedOdds

now = datetime.now(timezone.utc)
lo = now - timedelta(hours=2)
hi = now + timedelta(hours=24)

def make(hours_offset):
    from decimal import Decimal
    return NormalizedOdds(
        event_id='e1', sport_key='nba', sport_title='NBA',
        home_team='A', away_team='B',
        start_time=now + timedelta(hours=hours_offset),
        market_type='h2h', selection='A',
        book='draftkings', price=Decimal('-110'),
        market_key='k1',
    )

events = [make(-3), make(-1), make(12), make(30)]
filtered = [r for r in events if lo <= r.start_time <= hi]
assert len(filtered) == 2, f'Expected 2 events in window, got {len(filtered)}'
print('filter logic OK')
"
</automated>
  </verify>
  <done>
Events with start_time more than 2 hours in the past are excluded from arb/EV detection.
Events with start_time more than 24 hours in the future are excluded from arb/EV detection.
Events within the window pass through unchanged.
  </done>
</task>

</tasks>

<verification>
After both tasks complete, run the full test suite to confirm nothing is broken:

```bash
cd /Users/ringochui/Projects/chewyBot && python -m pytest tests/ -x -q 2>&1 | tail -20
```

If any existing arb scanner tests use mock events with hardcoded past start_times and they now
fail, those tests must be updated to use `datetime.now(UTC)` relative times instead of fixed
dates. That is a test data fix, not a logic regression.
</verification>

<success_criteria>
- config.ARB_LOOKBACK_HOURS and config.ARB_LOOKAHEAD_HOURS exist with correct defaults
- _run_scan() filters all_normalized by start_time window before detect_arb/detect_ev
- Stale events (Bruins vs Leafs from last week) would be silently dropped in production
- Far-future events (Lakers vs Warriors next week) would be silently dropped in production
- All existing tests pass (or failing tests are fixed to use relative times)
</success_criteria>

<output>
After completion, create `.planning/quick/260401-jzn-filter-out-stale-and-far-future-events-f/260401-jzn-SUMMARY.md`
</output>
