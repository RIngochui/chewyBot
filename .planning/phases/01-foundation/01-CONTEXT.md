# Phase 1: Foundation - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers the complete bot skeleton: entry point (bot.py) that loads all 5 cogs independently with error isolation, typed config (config.py via pydantic-settings), SQLite database layer with all 8 tables and PostgreSQL swap path documented, logging to rotating file + Discord channel via async queue handler, and all project deliverables (requirements.txt, .env.example, README.md, mock JSON files). No cog feature logic is implemented — only the infrastructure every cog depends on.

</domain>

<decisions>
## Implementation Decisions

### Startup & Slash Command Registration
- Fail fast on missing required env vars: collect all missing vars, raise a single descriptive error listing them all
- Register slash commands guild-specific (GUILD_ID) — instant sync, ideal for single-server deployment
- Startup Discord connection failure: retry 3× with exponential backoff, then exit with logged error
- Cog load failures: log error + full traceback to file, skip that cog and continue loading all others

### SQLite Setup
- SQLite file location: project root as `chewybot.db`
- Table initialization: `CREATE TABLE IF NOT EXISTS` on every startup (idempotent, safe)
- Enable WAL journal mode for concurrent read/write safety between auto-scanner and cog writes
- Seed bot_config table with defaults from env vars on startup (BANKROLL, MIN_ARB_PCT, MIN_EV_PCT, ENABLED_SPORTS, etc.)

### Discord Logging Handler
- Rate limit safety: async queue handler — drops messages gracefully if bot not ready, never blocks the event loop
- Discord channel receives WARNING+ only; file receives full INFO+ from all cogs
- File log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- Log rotation: RotatingFileHandler, 5MB max per file, 5 backup files

### Mock Data Design
- mock/odds_api_sample.json deliberately includes one guaranteed arbitrage opportunity (2-way moneyline where sum(1/odds) < 1.0) so the full arb pipeline is testable end-to-end
- 4–5 events across 3 sports (NBA, NFL, NHL) from fanduel, draftkings, betmgm, bet365
- mock/balldontlie_sample.json covers 8–10 NBA teams with last 5 game results each
- Includes edge case: same-game with opposing sides that should trigger deduplication logic

### Claude's Discretion
- Exact embed color hex value (spec says "not default blurple" — pick clean, consistent)
- README.md section ordering and exact prose
- requirements.txt version pinning strategy (exact pins vs compatible releases)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing code — greenfield project

### Established Patterns
- No existing patterns — all conventions established in this phase become the baseline for all subsequent phases

### Integration Points
- bot.py is the root — all cogs import from config.py, database/db.py, utils/logger.py
- The DB connection manager in db.py will be imported by every cog that persists data
- The logger setup in utils/logger.py must be called before any cog loads

</code_context>

<specifics>
## Specific Ideas

- Bot status: "chewyBot is online!" (from spec)
- Log channel ready message: "chewyBot has logged in!" (from spec)
- All 8 DB tables must be created: odds_snapshots, normalized_odds, arb_signals, ev_signals, parlays, parlay_legs, leg_type_weights, bot_config
- PostgreSQL swap path must be documented as a clear comment block in db.py (not just a note in README)
- Zero inline SQL anywhere except database/queries.py — enforced by code structure

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
