# Phase 3: Arbitrage Scanner - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 implements the Arbitrage Scanner cog — chewyBot's core value. It replaces all Phase 1 stubs: `adapters/odds_api.py`, `services/odds_normalizer.py`, `services/arb_detector.py`, `utils/odds_math.py`, `utils/formatters.py`, and creates the full `cogs/arb.py`. The scanner fetches live or mock odds, normalizes to a canonical schema, detects arb and +EV opportunities, deduplicates alerts, auto-scans every SCAN_INTERVAL_SECONDS, and posts actionable embeds to ARB_CHANNEL_ID. All 9 slash commands implemented.

</domain>

<decisions>
## Implementation Decisions

### OddsApiAdapter & API Behavior
- Mock mode: reload mock file on each scan — always fresh, catches edits during dev
- API error per sport: retry each sport 3x with exponential backoff, skip failed sport, continue scan — other sports still produce results
- Quota tracking: in-memory only (`_quota_remaining` attr) — refreshed each scan from response headers, not critical to persist across restart
- Sports list: `ENABLED_SPORTS` from config (comma-separated sport keys), toggleable at runtime via `/toggle_sport` — persisted to `bot_config`

### Signal Deduplication & Persistence
- Dedup key: `{event_id}_{market_key}` — unique per event+market, avoids cross-event collisions
- Dedup storage: in-memory dict `_seen: dict[str, float]` (dedup_key → last_alerted_pct) + full history in `arb_signals`/`ev_signals` DB tables
- Re-alert threshold: re-alert only if `arb_pct - last_alerted_pct > 0.2` (0.2% improvement per spec ARB-09)
- DB persistence: save ALL detected signals to DB regardless of threshold; Discord post only those above thresholds

### Auto-Scanner Architecture
- Background task: `discord.ext.tasks.loop(seconds=config.SCAN_INTERVAL_SECONDS)` — built-in discord.py, handles reconnects, `before_loop` / `after_loop` callbacks
- Scanner startup: start in `cog_load` — delivers core value from bot startup, no manual trigger needed
- Error handling: catch all exceptions, log to file + Discord, continue loop — never stops auto-scanning
- Scan feedback: silent — post to ARB_CHANNEL_ID only when alerts found; `/status` shows last scan time

### Claude's Discretion
- httpx client lifecycle (persistent client on adapter vs per-request)
- Exact embed layout and field ordering beyond spec requirements
- Stake calculation rounding (2 decimal places standard)
- Exact error message text for user-facing errors

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py`: `ODDS_API_KEY`, `ARB_CHANNEL_ID`, `BANKROLL`, `MIN_ARB_PCT`, `MIN_EV_PCT`, `SCAN_INTERVAL_SECONDS`, `ENABLED_SPORTS`, `MOCK_MODE`, `EMBED_COLOR`, `LOG_CHANNEL_ID` all available
- `database/db.py`: `get_db()` context manager — for saving signals, reading/writing bot_config
- `database/queries.py`: `UPSERT_BOT_CONFIG`, `GET_BOT_CONFIG_KEY` already written — reuse for /set_bankroll, /set_min_arb etc.
- `utils/logger.py`: logger setup ready — `logging.getLogger(__name__)` per module
- `models/odds.py`: `Market`, `OddsSnapshot`, `NormalizedOdds` — Pydantic v2 models ready
- `models/signals.py`: `ArbSignal`, `EVSignal` — signal models ready
- `adapters/base.py`: `SportsbookAdapter` ABC — implement `get_sports()`, `get_events()`, `get_odds()`
- `adapters/odds_api.py`: stub class with `BASE_URL`, `SUPPORTED_BOOKS`, `__init__` already written
- `services/arb_detector.py`: `detect_arb()`, `detect_ev()` stubs ready to implement
- `services/odds_normalizer.py`: `normalize()` stub ready to implement
- `utils/odds_math.py`: `american_to_decimal()`, `decimal_to_american()`, `implied_probability()`, `no_vig_probability()` stubs
- `utils/formatters.py`: embed builder stubs — implement arb and EV embed builders here
- `mock/odds_api_sample.json`: realistic mock data with guaranteed arb (10.1% arb) for testing
- `database/queries.py`: `arb_signals`/`ev_signals` tables already in schema (from Phase 1)

### Established Patterns
- Cog structure: `commands.Cog`, `cog_load()`, `setup(bot)`, guild-specific slash commands
- Error handling: log traceback to file, ephemeral error embed to user
- Config access: `self.bot.config` or pass config at cog init
- DB access: `async with get_db() as db: ...` pattern
- All SQL in `database/queries.py` only — zero inline SQL in services or cog

### Integration Points
- `cogs/arb.py` → `adapters/odds_api.py` → `services/odds_normalizer.py` → `services/arb_detector.py`
- `cogs/arb.py` → `utils/odds_math.py` (via services), `utils/formatters.py` (embed building)
- `cogs/arb.py` → `database/db.py` (signal persistence, config reads/writes)
- Alert language: NEVER "guaranteed profit" — always "possible arbitrage" / "estimated EV"

</code_context>

<specifics>
## Specific Ideas

- Alert embed disclaimer footer: "Not financial advice. Results are estimated and not guaranteed." (per CLAUDE.md safety constraint)
- `/status` embed fields: Current config (bankroll, min arb%, min EV%, enabled sports), Last scan time, API quota remaining, Scanner running: Yes/No
- `/latest_arbs` and `/latest_ev`: read from `arb_signals`/`ev_signals` DB tables, paginated, most recent first
- Arb alert embed fields per spec: sport, event, market, both sides (bookmaker + odds + stake), arb%, estimated profit, disclaimer
- +EV alert embed fields: sport, event, market, outcome, bookmaker, offered odds, fair odds, EV%
- `market_key` slug format: `{sport_key}_{home}_{away}_{market_type}` (lowercased, underscored)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
