---
phase: 01-foundation
plan: A
type: execute
wave: 1
depends_on: []
files_modified:
  - config.py
  - utils/logger.py
  - database/db.py
  - database/queries.py
autonomous: true
requirements: [BOT-02, BOT-04, BOT-06, BOT-07, DB-01, DB-02, DB-03, DB-04]

must_haves:
  truths:
    - "config.py raises a single descriptive error listing ALL missing env vars at startup — never a partial boot"
    - "setup_logging() attaches RotatingFileHandler (INFO+, 5MB/5 backups) and DiscordHandler (WARNING+) to the root logger"
    - "init_db() enables WAL mode and creates all 8 tables idempotently on every startup"
    - "Every function in all four files has full type hints — no bare 'def' without return type annotation"
    - "All SQL lives exclusively in database/queries.py — db.py contains zero SQL string literals"
    - "db.py has a comment block explaining exactly which two lines change to swap SQLite for PostgreSQL"
  artifacts:
    - path: "config.py"
      provides: "Typed Config object from .env via pydantic-settings v2"
      exports: ["Config", "config"]
    - path: "utils/logger.py"
      provides: "setup_logging() function wiring file + Discord handlers"
      exports: ["setup_logging", "DiscordHandler"]
    - path: "database/db.py"
      provides: "init_db() and get_db() async context manager"
      exports: ["init_db", "get_db"]
    - path: "database/queries.py"
      provides: "All SQL DDL and DML statements as Python constants"
      exports: ["CREATE_TABLES_SQL", "INSERT_BOT_CONFIG_DEFAULT", "GET_BOT_CONFIG"]
  key_links:
    - from: "bot.py (Phase C)"
      to: "config.py"
      via: "from config import config"
      pattern: "from config import config"
    - from: "database/db.py"
      to: "database/queries.py"
      via: "from database.queries import CREATE_TABLES_SQL"
      pattern: "from database.queries import"
    - from: "utils/logger.py"
      to: "discord bot instance"
      via: "bot parameter passed to setup_logging()"
      pattern: "setup_logging\\(bot"
---

<objective>
Build the three foundational infrastructure files that every subsequent cog and plan depends on: typed configuration (config.py), async logging (utils/logger.py), and database layer (database/db.py + database/queries.py).

Purpose: Without these, Plan B's models have no Config to reference, and Plan C's bot.py has no way to boot, persist data, or log.
Output: Four files establishing the core infrastructure contracts that all other files import from.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-RESEARCH.md

<interfaces>
<!-- Contracts this plan establishes for downstream consumers (Plans B and C). -->
<!-- Plan C (bot.py) imports: from config import config -->
<!-- Plan C (bot.py) calls: await init_db(), setup_logging(bot, config.LOG_CHANNEL_ID) -->
<!-- All cog stubs (Plan C) can import: from config import config -->

Config fields (all MUST be present — add __init__.py imports too):
  Required (no default — raises ValidationError if missing):
    DISCORD_TOKEN: str
    GUILD_ID: int
    LOG_CHANNEL_ID: int
    ODDS_API_KEY: str
    ARB_CHANNEL_ID: int
    PARLAY_CHANNEL_ID: int

  Optional with defaults:
    BANKROLL: float = 100.0
    MIN_ARB_PCT: float = 0.5
    MIN_EV_PCT: float = 2.0
    MIN_LEG_SCORE: float = 0.5
    SCAN_INTERVAL_SECONDS: int = 60
    PARLAY_POST_TIME: str = "11:00"
    PARLAY_LEARNING_RATE: float = 0.05
    TTS_INTERRUPTS_MUSIC: bool = False
    TTS_MAX_CHARS: int = 300
    MOCK_MODE: bool = False
    ENABLED_SPORTS: str = "basketball_nba,americanfootball_nfl,icehockey_nhl"

DB tables required (all 8):
  odds_snapshots, normalized_odds, arb_signals, ev_signals,
  parlays, parlay_legs, leg_type_weights, bot_config
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: config.py — typed pydantic-settings configuration with fail-fast validation</name>
  <files>config.py</files>
  <read_first>
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-CONTEXT.md (locked decisions section)
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-RESEARCH.md (Pattern 2: Pydantic-Settings)
  </read_first>
  <action>
Create config.py at the project root implementing pydantic-settings v2 Config class.

EXACT IMPLEMENTATION REQUIREMENTS:

1. Imports:
   ```python
   import sys
   from typing import Optional
   from pydantic import field_validator, ValidationError
   from pydantic_settings import BaseSettings, SettingsConfigDict
   ```

2. Class definition uses `model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)` (pydantic-settings v2 syntax — NOT the nested `class Config` pattern which is v1).

3. Required fields (no default — ValidationError raised if absent):
   - DISCORD_TOKEN: str
   - GUILD_ID: int
   - LOG_CHANNEL_ID: int
   - ODDS_API_KEY: str
   - ARB_CHANNEL_ID: int
   - PARLAY_CHANNEL_ID: int

4. Optional fields with defaults:
   - BANKROLL: float = 100.0
   - MIN_ARB_PCT: float = 0.5
   - MIN_EV_PCT: float = 2.0
   - MIN_LEG_SCORE: float = 0.5
   - SCAN_INTERVAL_SECONDS: int = 60
   - PARLAY_POST_TIME: str = "11:00"
   - PARLAY_LEARNING_RATE: float = 0.05
   - TTS_INTERRUPTS_MUSIC: bool = False
   - TTS_MAX_CHARS: int = 300
   - MOCK_MODE: bool = False
   - ENABLED_SPORTS: str = "basketball_nba,americanfootball_nfl,icehockey_nhl"

5. Full type hints on ALL methods. Add a `get_enabled_sports_list() -> list[str]` instance method that returns `self.ENABLED_SPORTS.split(",")`.

6. Module-level instantiation with fail-fast error handling (per D-01 locked decision):
   ```python
   try:
       config = Config()
   except ValidationError as e:
       missing = [err["loc"][0] for err in e.errors() if err["type"] == "missing"]
       invalid = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors() if err["type"] != "missing"]
       lines = []
       if missing:
           lines.append(f"Missing required env vars: {', '.join(str(m) for m in missing)}")
       if invalid:
           lines.extend(invalid)
       print("chewyBot configuration error:\n" + "\n".join(f"  - {l}" for l in lines))
       sys.exit(1)
   ```

7. EMBED_COLOR constant defined at module level: `EMBED_COLOR: int = 0x2E7D32` (dark green — consistent across all cogs, per BOT-05).

All functions and methods must have return type annotations. No bare `def`.
  </action>
  <verify>
    <automated>cd /Users/ringochui/Projects/chewyBot && python -c "import ast, sys; ast.parse(open('config.py').read()); print('syntax ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "SettingsConfigDict" config.py` returns 1 (pydantic-settings v2 syntax used)
    - `grep -c "DISCORD_TOKEN" config.py` returns at least 1 (required field present)
    - `grep -c "EMBED_COLOR" config.py` returns 1 (embed color constant defined)
    - `grep "EMBED_COLOR" config.py` shows `0x2E7D32`
    - `grep -c "sys.exit(1)" config.py` returns 1 (fail-fast implemented)
    - `grep -c "get_enabled_sports_list" config.py` returns 1 (helper method present)
    - `grep -n "def " config.py | grep -v "->"` returns empty (all defs have return type)
    - `python -c "import ast; ast.parse(open('config.py').read()); print('ok')"` prints "ok" (no syntax errors)
  </acceptance_criteria>
  <done>config.py exists with all 17 env vars, pydantic-settings v2 syntax, fail-fast error collection, EMBED_COLOR constant, and full type hints.</done>
</task>

<task type="auto">
  <name>Task 2: utils/logger.py — async Discord logging handler + rotating file handler</name>
  <files>utils/__init__.py, utils/logger.py</files>
  <read_first>
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-CONTEXT.md (Discord logging decisions)
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-RESEARCH.md (Pattern 4: Async Discord Logging Handler)
  </read_first>
  <action>
Create utils/__init__.py (empty) and utils/logger.py.

EXACT IMPLEMENTATION REQUIREMENTS:

1. Imports:
   ```python
   import asyncio
   import logging
   import logging.handlers
   from pathlib import Path
   import discord
   ```

2. LOG_FORMAT constant: `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` (exact format per locked decision)

3. LOG_FILE constant: `Path("chewybot.log")` (project root)

4. DiscordHandler class (inherits logging.Handler):
   - `__init__(self, bot: discord.Client, channel_id: int, level: int = logging.WARNING) -> None`
   - Stores `self.bot` and `self.channel_id`
   - `emit(self, record: logging.LogRecord) -> None`:
     - Returns immediately if `not self.bot.is_ready()` (drops message — never blocks)
     - Formats record with `self.format(record)`
     - Truncates to 1990 chars (Discord 2000 limit with buffer)
     - Wraps in code block: `` f"```\n{msg}\n```" ``
     - Schedules: `asyncio.create_task(self._send_to_discord(formatted))`
     - Wraps scheduling in try/except, calls `self.handleError(record)` on failure
   - `async def _send_to_discord(self, msg: str) -> None`:
     - Gets channel with `self.bot.get_channel(self.channel_id)`
     - Sends if channel is not None
     - Silent except block — never let Discord send failure break logging

5. `setup_logging(bot: discord.Client, log_channel_id: int) -> None` function:
   - Gets root logger: `logging.getLogger()`
   - Sets root logger level to `logging.DEBUG`
   - Creates RotatingFileHandler:
     - filename: `LOG_FILE`
     - maxBytes: `5 * 1024 * 1024` (5MB)
     - backupCount: 5
     - encoding: "utf-8"
     - level: `logging.INFO`
   - Creates DiscordHandler:
     - bot=bot, channel_id=log_channel_id
     - level: `logging.WARNING`
   - Sets formatter `logging.Formatter(LOG_FORMAT)` on BOTH handlers
   - Adds both handlers to root logger
   - Suppresses discord.py internal noise: `logging.getLogger("discord").setLevel(logging.WARNING)`

All functions and methods must have return type annotations. No bare `def`.
  </action>
  <verify>
    <automated>cd /Users/ringochui/Projects/chewyBot && python -c "import ast; ast.parse(open('utils/logger.py').read()); print('syntax ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "RotatingFileHandler" utils/logger.py` returns 1
    - `grep -c "5 \* 1024 \* 1024" utils/logger.py` returns 1 (5MB max size)
    - `grep -c "backupCount: 5\|backupCount=5" utils/logger.py` returns 1 (5 backups)
    - `grep "LOG_FORMAT" utils/logger.py` shows `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
    - `grep -c "is_ready" utils/logger.py` returns 1 (bot readiness check)
    - `grep -c "asyncio.create_task" utils/logger.py` returns 1 (async scheduling)
    - `grep -c "logging.WARNING" utils/logger.py` returns at least 2 (Discord handler level + discord.py suppression)
    - `grep -n "def " utils/logger.py | grep -v "->"` returns empty (all defs have return type)
    - `python -c "import ast; ast.parse(open('utils/logger.py').read()); print('ok')"` prints "ok"
    - `test -f utils/__init__.py` exits 0 (package init exists)
  </acceptance_criteria>
  <done>utils/__init__.py exists (empty). utils/logger.py exports setup_logging() and DiscordHandler with rotating file (INFO+, 5MB/5 backups) and async Discord handler (WARNING+).</done>
</task>

<task type="auto">
  <name>Task 3: database/db.py + database/queries.py — async SQLite layer with WAL and all 8 tables</name>
  <files>database/__init__.py, database/db.py, database/queries.py</files>
  <read_first>
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-CONTEXT.md (SQLite setup decisions)
    - /Users/ringochui/Projects/chewyBot/.planning/phases/01-foundation/01-RESEARCH.md (Pattern 3: SQLite Async Connection Manager)
  </read_first>
  <action>
Create database/__init__.py (empty), database/db.py, and database/queries.py.

--- database/queries.py ---

This file contains ALL SQL. Zero SQL string literals anywhere else. Structure:

1. Imports: none (pure constants)

2. CREATE_TABLES_SQL: list[str] — one CREATE TABLE IF NOT EXISTS statement per table.

All 8 tables with full column definitions:

```sql
-- odds_snapshots
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    market_key TEXT NOT NULL,
    book_name TEXT NOT NULL,
    sport TEXT NOT NULL,
    decimal_odds REAL NOT NULL,
    american_odds INTEGER NOT NULL,
    selection_name TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- normalized_odds
CREATE TABLE IF NOT EXISTS normalized_odds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    market_key TEXT NOT NULL,
    sport TEXT NOT NULL,
    league TEXT NOT NULL,
    event_name TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    market_type TEXT NOT NULL,
    selection_name TEXT NOT NULL,
    line_value REAL,
    decimal_odds REAL NOT NULL,
    american_odds INTEGER NOT NULL,
    book_name TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- arb_signals
CREATE TABLE IF NOT EXISTS arb_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL,
    event_name TEXT NOT NULL,
    sport TEXT NOT NULL,
    market_type TEXT NOT NULL,
    arb_pct REAL NOT NULL,
    stake_side_a REAL NOT NULL,
    stake_side_b REAL NOT NULL,
    estimated_profit REAL NOT NULL,
    book_a TEXT NOT NULL,
    book_b TEXT NOT NULL,
    odds_a REAL NOT NULL,
    odds_b REAL NOT NULL,
    selection_a TEXT NOT NULL,
    selection_b TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alerted INTEGER DEFAULT 0
)

-- ev_signals
CREATE TABLE IF NOT EXISTS ev_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_key TEXT NOT NULL,
    event_name TEXT NOT NULL,
    sport TEXT NOT NULL,
    market_type TEXT NOT NULL,
    selection_name TEXT NOT NULL,
    book_name TEXT NOT NULL,
    decimal_odds REAL NOT NULL,
    fair_probability REAL NOT NULL,
    ev_pct REAL NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    alerted INTEGER DEFAULT 0
)

-- parlays
CREATE TABLE IF NOT EXISTS parlays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_message_id TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    combined_odds REAL NOT NULL,
    confidence_score REAL NOT NULL,
    outcome TEXT DEFAULT 'pending',
    leg_count INTEGER NOT NULL
)

-- parlay_legs
CREATE TABLE IF NOT EXISTS parlay_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parlay_id INTEGER NOT NULL REFERENCES parlays(id),
    team TEXT NOT NULL,
    market_type TEXT NOT NULL,
    line_value REAL,
    american_odds INTEGER NOT NULL,
    leg_score REAL NOT NULL,
    leg_type TEXT NOT NULL,
    outcome TEXT DEFAULT 'pending'
)

-- leg_type_weights
CREATE TABLE IF NOT EXISTS leg_type_weights (
    leg_type TEXT PRIMARY KEY,
    weight REAL NOT NULL DEFAULT 1.0,
    hit_count INTEGER DEFAULT 0,
    miss_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)

-- bot_config
CREATE TABLE IF NOT EXISTS bot_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

3. Additional SQL constants for bot startup seeding:

```python
UPSERT_BOT_CONFIG = """
    INSERT INTO bot_config (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO NOTHING
"""

GET_BOT_CONFIG = "SELECT key, value FROM bot_config"

GET_BOT_CONFIG_KEY = "SELECT value FROM bot_config WHERE key = ?"
```

--- database/db.py ---

1. Imports:
   ```python
   import aiosqlite
   from pathlib import Path
   from contextlib import asynccontextmanager
   from collections.abc import AsyncGenerator
   from database.queries import CREATE_TABLES_SQL, UPSERT_BOT_CONFIG
   ```

2. DB_PATH constant: `Path("chewybot.db")` (project root per locked decision)

3. PostgreSQL swap comment block — MUST appear immediately before DB_PATH or as a module-level docstring. Exact text:
   ```python
   # ============================================================
   # PostgreSQL Migration: Replace SQLite with asyncpg
   # ============================================================
   # To swap SQLite for PostgreSQL, change exactly TWO things:
   #
   # 1. Replace this import:
   #    import aiosqlite
   #    with:
   #    import asyncpg
   #
   # 2. Replace the connection call in get_db() and init_db():
   #    aiosqlite.connect(str(DB_PATH))
   #    with:
   #    asyncpg.create_pool(dsn="postgresql://user:pass@host/dbname")
   #
   # Everything else (queries.py SQL, table names, column names)
   # remains unchanged — asyncpg uses the same parameterized query
   # syntax ($1, $2 vs ? — update queries.py placeholders too).
   # ============================================================
   ```

4. `async def init_db(bankroll: float = 100.0, min_arb_pct: float = 0.5, min_ev_pct: float = 2.0, enabled_sports: str = "basketball_nba,americanfootball_nfl,icehockey_nhl") -> None`:
   - Opens connection with `async with aiosqlite.connect(str(DB_PATH)) as db`
   - Executes `PRAGMA journal_mode=WAL`
   - Executes `PRAGMA synchronous=NORMAL`
   - Executes each statement in `CREATE_TABLES_SQL` (loop)
   - Seeds bot_config defaults using `UPSERT_BOT_CONFIG` for keys: "bankroll", "min_arb_pct", "min_ev_pct", "enabled_sports"
   - Commits after all table creation and seeding
   - Takes config values as parameters (bot.py passes config.BANKROLL etc.)

5. `@asynccontextmanager` decorated `async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]`:
   - Opens `aiosqlite.connect(str(DB_PATH))`
   - Sets `db.row_factory = aiosqlite.Row` for dict-like row access
   - Yields db
   - Commits on clean exit, rolls back on exception
   - `async with get_db() as db:` pattern for all callers

All functions must have full type hints and return annotations. Zero SQL strings in db.py — all SQL comes from queries.py imports.
  </action>
  <verify>
    <automated>cd /Users/ringochui/Projects/chewyBot && python -c "import ast; [ast.parse(open(f).read()) for f in ['database/db.py','database/queries.py']]; print('syntax ok')"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "CREATE TABLE IF NOT EXISTS" database/queries.py` returns 8 (all 8 tables)
    - `grep "CREATE TABLE IF NOT EXISTS" database/queries.py | wc -l | tr -d ' '` equals 8
    - `grep -c "bot_config\|parlays\|parlay_legs\|leg_type_weights\|arb_signals\|ev_signals\|normalized_odds\|odds_snapshots" database/queries.py` returns 8 (all table names present)
    - `grep -c "PostgreSQL Migration" database/db.py` returns 1 (swap comment block present)
    - `grep -c "PRAGMA journal_mode=WAL" database/db.py` returns 1 (WAL mode enabled)
    - `grep -c "asynccontextmanager" database/db.py` returns 1 (context manager decorator used)
    - `grep -c "row_factory" database/db.py` returns 1 (aiosqlite.Row set)
    - `grep -rn "CREATE TABLE\|INSERT INTO\|SELECT\|UPDATE\|DELETE" database/db.py` returns empty (no SQL in db.py)
    - `test -f database/__init__.py` exits 0
    - `python -c "import ast; ast.parse(open('database/db.py').read()); print('ok')"` prints "ok"
    - `python -c "import ast; ast.parse(open('database/queries.py').read()); print('ok')"` prints "ok"
  </acceptance_criteria>
  <done>database/__init__.py (empty), database/db.py with init_db(), get_db() context manager, WAL pragma, PostgreSQL swap comment, and zero inline SQL. database/queries.py with all 8 CREATE TABLE statements and bot_config UPSERT/GET constants.</done>
</task>

</tasks>

<verification>
After all three tasks complete, run from project root:

```bash
# All four files parse without errors
python -c "import ast; [ast.parse(open(f).read()) for f in ['config.py','utils/logger.py','database/db.py','database/queries.py']]; print('ALL SYNTAX OK')"

# config.py has all 17 env var fields
python -c "content = open('config.py').read(); vars = ['DISCORD_TOKEN','GUILD_ID','LOG_CHANNEL_ID','ODDS_API_KEY','ARB_CHANNEL_ID','PARLAY_CHANNEL_ID','BANKROLL','MIN_ARB_PCT','MIN_EV_PCT','SCAN_INTERVAL_SECONDS','MOCK_MODE','ENABLED_SPORTS','PARLAY_CHANNEL_ID','PARLAY_POST_TIME','PARLAY_LEARNING_RATE','TTS_INTERRUPTS_MUSIC','TTS_MAX_CHARS','MIN_LEG_SCORE']; missing = [v for v in vars if v not in content]; print('MISSING:', missing) if missing else print('ALL VARS PRESENT')"

# 8 tables in queries.py
python -c "content = open('database/queries.py').read(); count = content.count('CREATE TABLE IF NOT EXISTS'); print(f'{count}/8 tables')"

# No inline SQL in db.py
python -c "import re; content = open('database/db.py').read(); found = re.findall(r'\"\"\".*?SELECT|CREATE TABLE|INSERT INTO|UPDATE ', content, re.DOTALL); print('SQL found in db.py — FAIL' if found else 'No inline SQL — PASS')"
```
</verification>

<success_criteria>
- config.py: 17 env vars, pydantic-settings v2 syntax, fail-fast error with sys.exit(1), EMBED_COLOR=0x2E7D32, full type hints
- utils/logger.py: DiscordHandler (WARNING+, async, drops if bot not ready), RotatingFileHandler (INFO+, 5MB, 5 backups), LOG_FORMAT exact string, full type hints
- database/queries.py: 8 CREATE TABLE IF NOT EXISTS statements, UPSERT_BOT_CONFIG, GET_BOT_CONFIG, GET_BOT_CONFIG_KEY constants
- database/db.py: init_db() with WAL + table creation + bot_config seeding, get_db() async context manager, PostgreSQL swap comment block, zero inline SQL
- All files: full type hints, no syntax errors
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-A-SUMMARY.md` documenting:
- Files created and what they export
- EMBED_COLOR chosen (0x2E7D32)
- DB_PATH location (project root / chewybot.db)
- LOG_FORMAT string
- Any implementation decisions made during execution
</output>
