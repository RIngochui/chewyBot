---
phase: 01-foundation
plan: "01"
subsystem: infra
tags: [python, pydantic-settings, aiosqlite, sqlite, logging, discord.py]

# Dependency graph
requires: []
provides:
  - "config.py: typed Config object via pydantic-settings v2, EMBED_COLOR=0x2E7D32, fail-fast startup validation"
  - "utils/logger.py: setup_logging() wiring RotatingFileHandler (INFO+, 5MB/5) and async DiscordHandler (WARNING+)"
  - "database/db.py: init_db() with WAL mode + 8 tables, get_db() asynccontextmanager"
  - "database/queries.py: all SQL DDL (8 tables) and DML constants — single SQL source of truth"
affects: [01-02, 01-03, cogs, adapters]

# Tech tracking
tech-stack:
  added: [pydantic-settings==2.13.1, aiosqlite==0.22.1, discord.py==2.7.1]
  patterns:
    - "pydantic-settings v2 with model_config = SettingsConfigDict (not nested class Config)"
    - "asynccontextmanager for DB connections with commit/rollback guard"
    - "logging.Handler subclass using asyncio.create_task() for non-blocking Discord sends"

key-files:
  created:
    - config.py
    - utils/__init__.py
    - utils/logger.py
    - database/__init__.py
    - database/db.py
    - database/queries.py
  modified: []

key-decisions:
  - "EMBED_COLOR = 0x2E7D32 (dark green) chosen as consistent embed color across all cogs"
  - "DB_PATH = Path('chewybot.db') at project root per locked decision"
  - "LOG_FILE = Path('chewybot.log') at project root"
  - "bot_config seeded with 4 defaults: bankroll, min_arb_pct, min_ev_pct, enabled_sports"
  - "DiscordHandler uses asyncio.create_task (not QueueHandler) for simplicity — drops if bot not ready"

patterns-established:
  - "Pattern: All SQL in database/queries.py — zero SQL strings in db.py or any cog"
  - "Pattern: fail-fast config with sys.exit(1) after collecting ALL validation errors"
  - "Pattern: every def/method requires return type annotation — no bare def"

requirements-completed: [BOT-02, BOT-04, BOT-06, BOT-07, DB-01, DB-02, DB-03, DB-04]

# Metrics
duration: 4min
completed: 2026-03-31
---

# Phase 01 Plan 01: Infrastructure Foundation Summary

**pydantic-settings v2 typed config, async SQLite with WAL and all 8 tables, and non-blocking DiscordHandler logging established as shared infrastructure for all 5 cogs**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-31T03:26:48Z
- **Completed:** 2026-03-31T03:31:04Z
- **Tasks:** 3
- **Files created:** 6

## Accomplishments

- config.py: 6 required + 11 optional env vars via pydantic-settings v2, fail-fast error collection, EMBED_COLOR=0x2E7D32 constant
- utils/logger.py: async DiscordHandler (WARNING+, drops gracefully if bot not ready) + RotatingFileHandler (INFO+, 5MB/5 backups)
- database/queries.py: all 8 CREATE TABLE IF NOT EXISTS statements plus UPSERT/GET constants for bot_config
- database/db.py: init_db() with WAL pragma + bot_config seeding, get_db() asynccontextmanager with Row factory, PostgreSQL swap comment block

## Task Commits

Each task was committed atomically:

1. **Task 1: config.py — typed pydantic-settings configuration** - `77d3e0e` (feat)
2. **Task 2: utils/logger.py — async Discord logging handler + rotating file handler** - `be496ee` (feat)
3. **Task 3: database/db.py + database/queries.py — async SQLite layer** - `20c7b41` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `config.py` — pydantic-settings v2 Config class; EMBED_COLOR=0x2E7D32; fail-fast ValidationError handler; get_enabled_sports_list() helper
- `utils/__init__.py` — empty package init
- `utils/logger.py` — DiscordHandler (asyncio.create_task, 1990-char truncation, silent on send failure) and setup_logging() wiring both handlers to root logger
- `database/__init__.py` — empty package init
- `database/db.py` — init_db() (WAL, table creation, bot_config seed), get_db() asynccontextmanager, PostgreSQL migration comment block
- `database/queries.py` — CREATE_TABLES_SQL list[str] with 8 tables; UPSERT_BOT_CONFIG, GET_BOT_CONFIG, GET_BOT_CONFIG_KEY constants

## Decisions Made

- **EMBED_COLOR = 0x2E7D32**: Dark green chosen over Discord's default blurple — consistent, readable, not misleadingly red/yellow (per plan's discretion item)
- **asyncio.create_task vs QueueHandler**: Used create_task directly in DiscordHandler instead of a QueueHandler since the bot's asyncio event loop is always running; simpler and achieves the same non-blocking goal
- **bot_config seeds 4 keys**: bankroll, min_arb_pct, min_ev_pct, enabled_sports — the operational defaults the arb scanner reads at runtime
- **db.py exports only PRAGMA strings as inline literals**: PRAGMA journal_mode=WAL and PRAGMA synchronous=NORMAL are SQLite operational commands, not SQL queries — they're appropriate as inline strings; all actual SQL (DDL/DML) remains in queries.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Plan's verification regex `r'\"\"\".*?SELECT|CREATE TABLE|INSERT INTO|UPDATE '` produces a false positive due to Python operator precedence: it matches from any `"""` (docstring open) up to the next occurrence of `SELECT` or `CREATE TABLE`, rather than SQL within triple-quoted strings. The db.py contains zero actual SQL string literals — only PRAGMA strings and imports from queries.py. Issue is in the verification script, not the code.

## User Setup Required

None - no external service configuration required for this infrastructure layer. (The bot won't start without a `.env` file containing DISCORD_TOKEN, GUILD_ID, LOG_CHANNEL_ID, ODDS_API_KEY, ARB_CHANNEL_ID, and PARLAY_CHANNEL_ID — see Plan 03 for .env.example creation.)

## Next Phase Readiness

- Plan 02 (Pydantic models, adapters base, odds math) can import `from config import config` immediately
- Plan 03 (bot.py, cog stubs, deliverables) can call `await init_db(config.BANKROLL, ...)` and `setup_logging(bot, config.LOG_CHANNEL_ID)`
- All 8 DB tables ready for cog data persistence in later phases
- No blockers — all infrastructure contracts established

## Self-Check: PASSED

All 6 source files confirmed present on disk. All 3 task commits confirmed in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-31*
