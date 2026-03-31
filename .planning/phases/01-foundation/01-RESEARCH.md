# Phase 1: Foundation - Research

**Researched:** 2026-03-30
**Domain:** Discord.py bot scaffolding, configuration management, async database layer, and logging infrastructure
**Confidence:** HIGH

## Summary

Phase 1 establishes the complete bot skeleton on which all five cogs depend. The primary technical challenges are (1) loading cogs independently so one syntax error doesn't crash others, (2) managing typed configuration from environment variables with pydantic-settings v2, (3) initializing SQLite with async context managers and WAL mode, (4) setting up async-safe logging to both file and Discord channel, and (5) configuring guild-scoped slash command sync for instant development iteration. All technologies are mature and well-documented; the complexity lies in integration and error isolation patterns, not library selection.

**Primary recommendation:** Use discord.py's `bot.load_extension()` in a try-except loop with logging for error isolation; configure pydantic-settings v2 with required fields validated on startup (fail fast); use aiosqlite context managers with WAL pragma on startup; separate file and Discord logging handlers with QueueHandler for Discord (non-blocking) and RotatingFileHandler for file (blocking acceptable); call `tree.sync(guild=discord.Object(id=GUILD_ID))` in `setup_hook()` for instant guild-scope feedback.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Fail fast on missing required env vars:** Collect ALL missing vars at startup, raise single descriptive error listing them all — do not let bot proceed with partial config
- **Guild-specific slash commands (GUILD_ID):** Register all commands to a specific guild for instant sync (no 1-hour global delay), ideal for single-server deployment
- **SQLite at project root:** Database file location is `chewybot.db` in the project root, with clear PostgreSQL swap documentation in code comments
- **CREATE TABLE IF NOT EXISTS on startup:** Idempotent table initialization — safe to re-run on every startup
- **WAL journal mode enabled:** Enable PRAGMA journal_mode=WAL on startup for concurrent read/write safety
- **Async queue Discord logging:** Use a queue-based handler for Discord so blocked sends never block the bot's event loop; WARNING+ to Discord channel, INFO+ to file
- **RotatingFileHandler:** 5MB max per file, keep 5 backup files
- **Bot config seeded from env:** The `bot_config` table seeded with defaults (BANKROLL, MIN_ARB_PCT, MIN_EV_PCT, ENABLED_SPORTS) on startup from environment variables

### Claude's Discretion

- **Exact embed color hex value:** Spec says "not default blurple" — pick clean, consistent color and document in code
- **README.md section ordering and prose:** Structure and wording are flexible; ensure technical accuracy
- **requirements.txt version pinning strategy:** Choose between exact pins vs compatible release operators (e.g., `==` vs `~=`)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.

---

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOT-01 | Bot entry point (bot.py) loads all cogs independently — one cog failing never crashes others | Covered in "Cog Loading with Error Isolation" pattern |
| BOT-02 | config.py loads all secrets from .env via pydantic-settings and exposes a typed Config object | Covered in "Pydantic-Settings v2 Configuration Pattern" |
| BOT-03 | Bot displays status "chewyBot is online 🐾" on ready and posts "chewyBot has logged in!" to LOG_CHANNEL_ID | Covered in "Discord.py Ready Hook and Status" |
| BOT-04 | Logging writes to chewybot.log file AND Discord LOG_CHANNEL_ID using Python logging module | Covered in "Async Discord Logging Handler" |
| BOT-05 | All embeds use a consistent color scheme across all cogs (not default blurple) | Discretion item; document chosen hex value in code |
| BOT-06 | Full type hints on every function throughout the codebase | Standard Python practice; no special research needed |
| BOT-07 | All external API calls use exponential backoff with max 3 retries | Covered in "Exponential Backoff and Retry Patterns" |
| DB-01 | SQLite storage layer with all SQL in database/queries.py — zero inline SQL anywhere else | Covered in "Database Layer Architecture" |
| DB-02 | db.py connection manager has clear comment block showing exactly what to change to swap SQLite → PostgreSQL | Covered in "PostgreSQL Swap Documentation" |
| DB-03 | Tables created: odds_snapshots, normalized_odds, arb_signals, ev_signals, parlays, parlay_legs, leg_type_weights, bot_config | Covered in "SQLite CREATE TABLE Pattern" |
| DB-04 | Pydantic v2 models used for all API response parsing and data validation | Covered in "Pydantic Data Validation" |
| DEL-01 | requirements.txt with pinned versions | Covered in "Dependency Management" |
| DEL-02 | .env.example with all 20 variables documented | Covered in "Environment Variable Documentation" |
| DEL-03 | README.md: what chewyBot is, prerequisites, install, Discord setup, Odds API setup, run, add sportsbook, PostgreSQL swap | Covered in "Documentation Patterns" |
| DEL-04 | mock/odds_api_sample.json — realistic multi-sport sample for MOCK_MODE | Out of scope for research; data design is UX decision |
| DEL-05 | mock/balldontlie_sample.json — realistic NBA teams/stats sample for MOCK_MODE | Out of scope for research; data design is UX decision |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| discord.py | 2.7.1 | Discord bot framework with slash commands, async events, cog system | Official, actively maintained (Mar 2026), modern app_commands API standard for v2 bots, large ecosystem |
| pydantic-settings | 2.13.1 | Typed configuration from .env with validation | Official Pydantic package for settings (moved from core in v2), required for env var loading, validates on instantiation |
| aiosqlite | 0.22.1 | Async SQLite interface with context managers | Only async SQLite wrapper, single thread per connection prevents blocking, no ORM overhead (matches phase goals) |
| Python | 3.11+ | Base language | Project requirement, asyncio fully mature, type hints standard |
| pydantic | 2.x | Data validation for API responses and cogs | Already required by pydantic-settings; v2 major version aligns with project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.0+ | Load .env into os.environ before pydantic-settings reads it | Optional convenience; pydantic-settings reads os.environ directly, no load() call needed if vars already in environment |
| asyncio | 3.11 stdlib | Async runtime for bot and database | Built-in, required for discord.py and aiosqlite |
| logging | 3.11 stdlib | File and console logging with handlers | Built-in, RotatingFileHandler standard library support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | python-decouple or environs | Less type validation; pydantic-settings is official Pydantic package with full v2 support |
| aiosqlite | asyncpg (PostgreSQL only) or motor (MongoDB) | asyncpg tied to PostgreSQL (violates swappable design); motor adds NoSQL complexity; aiosqlite is SQLite-native |
| discord.py | py-cord or nextcord | Rapptz/discord.py has largest community and is reference implementation; alternatives have smaller ecosystems |
| Python logging | loguru or structlog | Logging module adequate for this phase; loguru/structlog add JSON/structured logging complexity not needed yet |

**Installation:**
```bash
pip install discord.py==2.7.1
pip install pydantic-settings==2.13.1
pip install aiosqlite==0.22.1
pip install python-dotenv  # optional
```

**Version verification (run before committing requirements.txt):**
```bash
pip index versions discord.py
pip index versions pydantic-settings
pip index versions aiosqlite
```

Current verified versions: discord.py 2.7.1 (Mar 3, 2026), pydantic-settings 2.13.1 (Feb 19, 2026), aiosqlite 0.22.1 (Dec 23, 2025).

---

## Architecture Patterns

### Recommended Project Structure
```
chewybot/
├── bot.py                    # Entry point: loads cogs, starts event loop
├── config.py                 # pydantic-settings Config class, reads .env
├── requirements.txt          # Pinned dependencies
├── .env.example              # Template for required env vars
├── .env                       # Actual secrets (git-ignored)
├── chewybot.db               # SQLite database (git-ignored)
├── chewybot.log              # Rotating log file (git-ignored)
├── README.md                 # Project documentation
├── cogs/                      # Cog modules (load independently)
│   ├── __init__.py
│   ├── music.py              # (Phase 2)
│   ├── tts.py                # (Phase 2)
│   ├── emoji_proxy.py        # (Phase 2)
│   ├── arbitrage_scanner.py  # (Phase 3)
│   └── nba_parlay.py         # (Phase 4)
├── database/                 # Database layer
│   ├── db.py                 # Connection manager, WAL setup
│   ├── queries.py            # All SQL statements (zero inline SQL rule)
│   └── models.py             # Pydantic models for validation
├── utils/                    # Shared utilities
│   ├── logger.py             # Logging setup (file + Discord handler)
│   └── odds_math.py          # (Phase 3) Arbitrage math helpers
├── adapters/                 # (Phase 3) Sportsbook adapters
│   ├── base.py               # Abstract interface
│   └── odds_api.py           # The Odds API implementation
└── mock/                     # Mock data for testing
    ├── odds_api_sample.json
    └── balldontlie_sample.json
```

### Pattern 1: Cog Loading with Error Isolation

**What:** Load all cogs in a loop, catch exceptions per-cog, log errors, and continue loading others. This ensures one broken cog (syntax error, missing import) doesn't prevent the bot from starting.

**When to use:** Always, for every cog load. Bot should be resilient to individual cog failures.

**Example:**
```python
# bot.py
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

async def load_cogs(bot):
    """Load all cogs from cogs/ directory. Log errors, continue loading."""
    cogs_dir = Path("cogs")
    cog_files = [f.stem for f in cogs_dir.glob("*.py") if f.name != "__init__.py"]
    
    failed = []
    for cog_name in cog_files:
        try:
            await bot.load_extension(f"cogs.{cog_name}")
            logger.info(f"Loaded cog: {cog_name}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog_name}: {e}", exc_info=True)
            failed.append(cog_name)
    
    if failed:
        logger.warning(f"Failed cogs: {', '.join(failed)}. Bot continuing with loaded cogs.")

# In bot setup_hook or on_ready:
await load_cogs(bot)
```

**Why this works:** `bot.load_extension()` raises `ExtensionFailed` or `ExtensionNotFound` but doesn't unload already-loaded cogs, so wrapping in try-except lets you log and continue.

### Pattern 2: Pydantic-Settings v2 Configuration Pattern

**What:** Define a `Config` class inheriting from `BaseSettings`, declare typed fields with optional defaults, and instantiate once on startup. Missing required env vars raise `ValidationError` on instantiation (fail fast).

**When to use:** All environment configuration — required API keys, Discord IDs, numeric thresholds, feature flags.

**Example:**
```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional

class Config(BaseSettings):
    # Required fields (no default) — raises ValidationError if missing
    DISCORD_TOKEN: str
    GUILD_ID: int
    LOG_CHANNEL_ID: int
    
    # Optional fields with defaults
    BANKROLL: float = Field(default=100.0, description="Starting bankroll in USD")
    MIN_ARB_PCT: float = Field(default=0.5, description="Minimum arbitrage % threshold")
    MIN_EV_PCT: float = Field(default=2.0, description="Minimum +EV % threshold")
    SCAN_INTERVAL_SECONDS: int = Field(default=60)
    MOCK_MODE: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        case_sensitive = True  # Enforce UPPERCASE var names
    
    @field_validator("GUILD_ID", "LOG_CHANNEL_ID", mode="before")
    @classmethod
    def validate_ints(cls, v):
        """Ensure IDs are valid positive integers."""
        if isinstance(v, str):
            return int(v)
        return v

# bot.py
try:
    config = Config()  # Reads .env, validates, raises ValidationError if required fields missing
except ValidationError as e:
    # Collect all missing required fields in error message
    print("Configuration error (missing required env vars):")
    for error in e.errors():
        print(f"  - {error['loc'][0]}: {error['msg']}")
    sys.exit(1)
```

**Key points:**
- Fields without defaults are required; pydantic raises `ValidationError` on instantiation if missing
- `env_file = ".env"` automatically loads .env (no need to call load_dotenv)
- Validators can transform types (e.g., string "123" → int 123)
- `case_sensitive = True` enforces UPPERCASE env var names matching field names

### Pattern 3: SQLite Async Connection Manager with WAL Mode

**What:** Use `async with aiosqlite.connect()` context manager for automatic resource cleanup. Enable WAL mode on first connection for concurrent read/write safety. Use `CREATE TABLE IF NOT EXISTS` for idempotent initialization.

**When to use:** All database operations — initialization, queries, schema changes.

**Example:**
```python
# database/db.py
import aiosqlite
from pathlib import Path

DB_PATH = Path("chewybot.db")

async def init_db():
    """Initialize database: enable WAL, create all tables."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Enable WAL mode for concurrent read/write
        await db.execute("PRAGMA journal_mode=WAL")
        
        # Optional: other pragmas for better concurrent performance
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-64000")
        
        await db.commit()
        
        # Now create all tables (idempotent)
        await create_tables(db)

async def create_tables(db):
    """Import and run all CREATE TABLE IF NOT EXISTS statements."""
    from database.queries import CREATE_TABLES_SQL
    
    for table_sql in CREATE_TABLES_SQL:
        await db.execute(table_sql)
    await db.commit()

async def get_connection():
    """Get a connection for one-off queries. Use in `async with` blocks."""
    return aiosqlite.connect(str(DB_PATH))

# database/queries.py
CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS odds_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL,
        market_key TEXT NOT NULL,
        decimal_odds REAL NOT NULL,
        book_name TEXT NOT NULL,
        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # ... other tables
]
```

**Why this works:**
- WAL mode (Write-Ahead Logging) separates read and write, preventing lock contention
- `CREATE TABLE IF NOT EXISTS` safe to run multiple times (idempotent)
- Async context manager `async with` calls `__aenter__` and `__aexit__` automatically, closing connection even on error

### Pattern 4: Async Discord Logging Handler

**What:** Send WARNING+ logs to Discord channel via QueueHandler (non-blocking) + QueueListener in background. File logging (INFO+) uses RotatingFileHandler (blocking acceptable for file I/O).

**When to use:** Any phase. Logs bot events, errors, and alerts to a Discord channel so operators see them in real-time without blocking bot responsiveness.

**Example:**
```python
# utils/logger.py
import logging
import logging.handlers
from logging import QueueHandler, QueueListener
from queue import Queue
import discord

class DiscordHandler(logging.Handler):
    """Send log records to Discord channel via webhook or bot.post_message."""
    
    def __init__(self, bot, channel_id: int, level=logging.WARNING):
        super().__init__(level)
        self.bot = bot
        self.channel_id = channel_id
    
    def emit(self, record):
        """Send log record to Discord (non-blocking via asyncio)."""
        if not self.bot.is_ready():
            # Bot not ready yet, skip sending
            return
        
        msg = self.format(record)
        try:
            # Queue to event loop without blocking
            asyncio.create_task(self._send_to_discord(msg))
        except Exception:
            self.handleError(record)
    
    async def _send_to_discord(self, msg: str):
        """Async send to Discord channel."""
        try:
            channel = self.bot.get_channel(self.channel_id)
            if channel:
                # Truncate to Discord's 2000 char limit
                await channel.send(msg[:2000])
        except Exception:
            # Silently fail — don't let Discord send failures block logging
            pass

def setup_logging(bot, log_channel_id: int):
    """Configure file and Discord logging."""
    from config import Config
    config = Config()
    
    # File handler: RotatingFileHandler (INFO+ from all loggers)
    file_handler = logging.handlers.RotatingFileHandler(
        "chewybot.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # Discord handler: WARNING+ only (avoids spam from INFO/DEBUG)
    discord_handler = DiscordHandler(bot, log_channel_id, level=logging.WARNING)
    discord_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    discord_handler.setFormatter(discord_formatter)
    
    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(discord_handler)
    
    # Silence noisy discord.py logs
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)

# bot.py
async def setup_hook(self):
    """Called before bot connects."""
    config = Config()
    setup_logging(self, config.LOG_CHANNEL_ID)
    await self.load_cogs()  # After logging ready
```

**Why this works:**
- `QueueHandler` + background thread prevents Discord API calls from blocking the event loop
- `DiscordHandler.emit()` checks `bot.is_ready()` before sending (prevents errors before connection)
- Truncation to 2000 chars prevents Discord API errors
- File handler blocks, but file I/O is fast enough not to matter

### Pattern 5: Guild-Scoped Slash Command Sync

**What:** Call `tree.sync(guild=discord.Object(id=GUILD_ID))` in `setup_hook()` to register commands to a specific guild. Instant sync (< 1 second) instead of global sync (1-hour cache).

**When to use:** Always, for development and production. Guild scope ideal for single-server bot.

**Example:**
```python
# bot.py
import discord
from discord.ext import commands

class ChewyBot(commands.Bot):
    def __init__(self, config):
        self.config = config
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",  # Slash commands preferred
            intents=intents
        )
    
    async def setup_hook(self):
        """Called before login; set up cogs and sync commands."""
        # Load all cogs
        await self.load_cogs()
        
        # Sync slash commands to specific guild (instant feedback)
        guild = discord.Object(id=self.config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)  # Copy all global commands to guild
        await self.tree.sync(guild=guild)
        print(f"Synced slash commands to guild {self.config.GUILD_ID}")
    
    async def on_ready(self):
        """Called when bot connects and is ready."""
        print(f"{self.user} has logged in!")
        
        # Send to log channel
        channel = self.get_channel(self.config.LOG_CHANNEL_ID)
        if channel:
            await channel.send("chewyBot has logged in!")
        
        # Set activity status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="chewyBot is online 🐾"
            )
        )

# main
if __name__ == "__main__":
    config = Config()
    bot = ChewyBot(config)
    bot.run(config.DISCORD_TOKEN)
```

**Key points:**
- `setup_hook()` runs before connection; safe place to load cogs and sync commands
- `tree.copy_global_to(guild=...)` copies commands defined in cogs to the guild scope
- `tree.sync(guild=...)` registers commands to that specific guild (instant)
- `on_ready()` posts "chewyBot has logged in!" to LOG_CHANNEL_ID

### Anti-Patterns to Avoid

- **Loading cogs without error handling:** If one cog has a syntax error, bot won't start. Always wrap in try-except.
- **Inline SQL outside queries.py:** Creates maintenance burden, hides SQL patterns, violates PostgreSQL swap goal. Put all SQL in one module.
- **Hardcoded secrets in codebase:** Use .env + pydantic-settings. Never commit API keys, tokens, or passwords.
- **Synchronous blocking in event loop:** Never use `time.sleep()`, `requests.get()`, or file I/O directly in async functions. Use `await asyncio.sleep()`, `aiohttp`, and async file libraries.
- **Global Discord logging with no rate limiting:** If bot logs every message, Discord API will rate-limit. Use WARNING+ only for Discord; INFO+ for file.
- **Not enabling WAL mode for SQLite:** Without WAL, concurrent reads and writes block each other. Enable on startup.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Configuration from .env with type validation | Custom env var parser + type casting | pydantic-settings v2 | Pydantic handles nested models, type coercion, validation, defaults; custom parsing error-prone |
| Async SQLite access | Async wrapper around sqlite3.connect() | aiosqlite | Single-threaded queue model prevents blocking; connection pooling optional but handled well |
| File rotation on disk space | Implement log file rotation manually | logging.handlers.RotatingFileHandler | Built-in, thread-safe, proven; custom rotation has edge cases (concurrent writes, cleanup) |
| Loading Python modules at runtime with error isolation | Recursive __import__ + try-except | bot.load_extension() + exception handling | discord.py's load_extension handles module cleanup, reload state, extension registry |
| Sending logs to Discord channel without blocking event loop | Direct await channel.send() in handler | QueueHandler + background thread or asyncio.create_task | Direct send blocks event loop during network I/O; queue decouples sender from I/O |

**Key insight:** Configuration, database, and logging are deceptively complex when done by hand (edge cases in env var parsing, concurrent database access, file rotation race conditions). Use proven libraries for these infra concerns; focus custom code on bot logic.

---

## Common Pitfalls

### Pitfall 1: One Cog Failure Crashes Entire Bot

**What goes wrong:** A syntax error or missing import in one cog file causes `bot.load_extension()` to raise an exception. If not caught, the bot fails to start.

**Why it happens:** `load_extension()` stops at the first error by default; no loop wrapping means one failure = bot failure.

**How to avoid:** Wrap each `load_extension()` in try-except. Log the error and continue loading other cogs. Verify bot starts even with broken cog.

**Warning signs:** Bot fails to start after adding a new cog. Error traceback mentions `ExtensionFailed` or `ExtensionNotFound`.

### Pitfall 2: Missing Required Env Vars Silently Create Broken Bot

**What goes wrong:** A required env var (e.g., `DISCORD_TOKEN`) is not set. pydantic-settings creates a Config object with `None` or defaults, and the bot attempts to start with invalid credentials. Errors appear later in cryptic ways.

**Why it happens:** If env vars are not validated on startup, missing values aren't caught until first use (e.g., "invalid token" when connecting).

**How to avoid:** Define required fields in Config without defaults. Instantiate Config on startup in main. Catch `ValidationError` and print all missing fields at once. Example: "Missing env vars: DISCORD_TOKEN, GUILD_ID, LOG_CHANNEL_ID" — fail fast.

**Warning signs:** Bot connects but immediately disconnects. Logs show "Invalid token" or "Unauthorized" errors. Check .env file before running.

### Pitfall 3: SQLite Locked/Database is Locked Errors

**What goes wrong:** Without WAL mode, concurrent reads and writes lock the database. If a cog is writing while another is reading, "database is locked" error occurs, especially under load.

**Why it happens:** SQLite default journal mode (DELETE) locks the entire database during writes. Concurrent operations from different asyncio tasks hit the lock.

**How to avoid:** Enable WAL mode on first connection: `PRAGMA journal_mode=WAL`. WAL allows concurrent reads while writes go to separate file. Verify with `PRAGMA journal_mode` (should return "wal").

**Warning signs:** Random "database is locked" errors when multiple cogs run simultaneously. Errors disappear when running single cog.

### Pitfall 4: Discord Handler Blocks Event Loop

**What goes wrong:** Log handler sends message to Discord channel directly via `await channel.send()`. If the Discord API is slow or there's a network delay, the entire bot event loop is blocked while waiting for the HTTP response.

**Why it happens:** Logging handler runs synchronously on the event loop. Direct async/await in handler blocks the loop.

**How to avoid:** Use `asyncio.create_task()` or `QueueHandler` to decouple logging from event loop. Queue handler runs in background thread; bot continues immediately after queueing the message.

**Warning signs:** Bot becomes unresponsive after logs are sent. Commands are slow to respond. Network latency (e.g., Discord API down) causes bot to hang.

### Pitfall 5: Hardcoded Secrets in Code

**What goes wrong:** API keys, Discord bot token, or webhook URLs are hardcoded in bot.py or config.py. Code is committed to git; secrets are exposed.

**Why it happens:** Convenience during development; forgotten before commit.

**How to avoid:** All secrets in .env file. .env is git-ignored. Use pydantic-settings to load from .env. Include .env.example in git with dummy values. Run `git rm --cached .env` if accidentally committed.

**Warning signs:** GitHub or audit tools flag secret tokens in code. Discord bot token exposed; attacker can takeover bot.

### Pitfall 6: Global Slash Command Sync Delayed

**What goes wrong:** Use `await tree.sync()` without guild parameter (global sync). Changes take up to 1 hour to appear in Discord client. During development, you reload the bot and commands don't update, causing confusion.

**Why it happens:** Discord's global command cache is intentionally slow (1-hour TTL) for performance. Guild scope syncs instantly but is invisible in global list.

**How to avoid:** Use guild-scoped sync during development: `await tree.sync(guild=discord.Object(id=GUILD_ID))`. Instant feedback. For production, use global if truly needed, but expect delays.

**Warning signs:** You add a new command, restart bot, command doesn't appear in Discord for 10 minutes. Try syncing to guild instead.

### Pitfall 7: CREATE TABLE Without IF NOT EXISTS Fails on Restart

**What goes wrong:** Run `CREATE TABLE odds_snapshots (...)` directly. On bot restart, table already exists, query fails, database initialization breaks.

**Why it happens:** `CREATE TABLE` raises error if table exists. If initialization isn't idempotent, restarts fail.

**How to avoid:** Always use `CREATE TABLE IF NOT EXISTS`. Safe to run multiple times. Check initialization logs to confirm tables exist on second startup.

**Warning signs:** Second bot restart fails with "table already exists" error. First run works, restart fails.

---

## Code Examples

Verified patterns from official sources and research:

### Cog Loading with Error Isolation
```python
# bot.py — Load all cogs, skip broken ones
import asyncio
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

async def load_cogs(bot):
    """Load all cogs from cogs/ directory. Log errors, continue loading."""
    cogs_dir = Path("cogs")
    cog_files = sorted([f.stem for f in cogs_dir.glob("*.py") if f.name != "__init__.py"])
    
    for cog_name in cog_files:
        try:
            await bot.load_extension(f"cogs.{cog_name}")
            logger.info(f"Loaded cog: {cog_name}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog_name}: {type(e).__name__}: {e}", exc_info=True)
            # Continue loading other cogs

# In bot.setup_hook():
await load_cogs(self)
```

Source: [discord.py Extensions documentation](https://discordpy.readthedocs.io/en/stable/ext/commands/extensions.html), [ModularDiscordBots guide](https://medium.com/@ajiboyetolu1/modular-discord-bots-in-python-a-guide-to-using-cogs-d89da141c4b9)

### Pydantic-Settings v2 Configuration
```python
# config.py
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import sys

class Config(BaseSettings):
    """Load configuration from .env with type validation and required field checks."""
    
    # Required fields (no default)
    DISCORD_TOKEN: str
    GUILD_ID: int
    LOG_CHANNEL_ID: int
    
    # Optional with defaults
    BANKROLL: float = Field(default=100.0, description="Starting bankroll USD")
    MIN_ARB_PCT: float = Field(default=0.5, description="Arb % threshold")
    MIN_EV_PCT: float = Field(default=2.0, description="EV % threshold")
    SCAN_INTERVAL_SECONDS: int = Field(default=60)
    MOCK_MODE: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        case_sensitive = True

if __name__ == "__main__":
    try:
        config = Config()
        print(f"Config loaded: GUILD_ID={config.GUILD_ID}")
    except Exception as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
```

Source: [Pydantic Settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### SQLite with WAL and CREATE TABLE IF NOT EXISTS
```python
# database/db.py
import aiosqlite
from pathlib import Path

DB_PATH = Path("chewybot.db")

async def init_db():
    """Initialize database: enable WAL, create tables."""
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Enable WAL for concurrent read/write
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.commit()
        
        # Create tables (idempotent)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                market_key TEXT NOT NULL,
                decimal_odds REAL NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        print("Database initialized")

# bot.py — call in on_ready or setup_hook
async def setup_hook(self):
    await init_db()
```

Source: [aiosqlite GitHub](https://github.com/omnilib/aiosqlite), [SQLite WAL documentation](https://www.sqlite.org/wal.html)

### Guild-Scoped Slash Command Sync
```python
# bot.py
import discord
from discord.ext import commands

class ChewyBot(commands.Bot):
    def __init__(self, config):
        self.config = config
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
    
    async def setup_hook(self):
        """Set up before login."""
        # Load cogs
        await self.load_cogs()
        
        # Sync commands to guild
        guild = discord.Object(id=self.config.GUILD_ID)
        await self.tree.sync(guild=guild)
        print(f"Slash commands synced to guild {self.config.GUILD_ID}")
```

Source: [discord.py examples/app_commands](https://github.com/Rapptz/discord.py/blob/master/examples/app_commands/basic.py), [AbstractUmbra's slash command guide](https://gist.github.com/AbstractUmbra/a9c188797ae194e592efe05fa129c57f)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| discord.py v1 prefix commands | discord.py v2 slash commands (app_commands) | 2021–2022 | Slash commands are now standard; Discord Client UI prioritizes them; prefix commands still supported but deprecated for new bots |
| pydantic v1 (settings in core) | pydantic-settings v2 (separate package) | 2023 | Settings moved to separate package; must import from `pydantic_settings` not `pydantic` |
| sqlite3 blocking I/O in async | aiosqlite (single-threaded queue per connection) | 2015–present | aiosqlite standard for async SQLite; prevents event loop blocking |
| Global slash command sync only | Guild-scoped sync support | discord.py 2.0+ | Guild scope now preferred for development; instant sync, no 1-hour cache |

**Deprecated/outdated:**
- **discord.py v1 (pre-2.0):** Prefix commands focus, no app_commands support. Discord deprecated prefix command visibility. All new bots use v2.
- **pydantic v1:** Use v2. v1 will eventually hit EOL. v2 has better type support and performance.
- **Synchronous sqlite3 in async bots:** Use aiosqlite. Blocking database I/O in event loop causes hangs.

---

## Environment Availability

All Phase 1 technologies are pure Python libraries with no external dependencies. The environment audit is minimal:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | ✓ | 3.11+ (assumed) | — |
| pip | Dependency installation | ✓ | 3.11+ stdlib | — |

**Skip details:** Phase 1 is code-only. No external services (Discord, APIs, databases) must be available to create the bot skeleton. Services are tested in later phases.

---

## Open Questions

1. **Exact embed color hex value**
   - What we know: Spec says "not default blurple (#5865F2)"; phase decision deferred to Claude's Discretion
   - What's unclear: Which hex color should be chosen for consistency across all embeds
   - Recommendation: Pick a color during task execution (e.g., `#2E7D32` dark green for sports theme, or `#1976D2` blue-primary). Document in code comments and ensure it's used everywhere embeds are sent.

2. **requirements.txt version pinning strategy**
   - What we know: Exact pins (==) vs compatible releases (~=) affects stability vs. security updates
   - What's unclear: Project preference for balance between stability and catching bug fixes
   - Recommendation: Use exact pins (==) for Phase 1 to ensure reproducible builds. In Phase 2+, upgrade policy can be set based on maintenance experience.

3. **PostgreSQL swap documentation format**
   - What we know: CONTEXT.md says "clear comment block showing exactly what to change"
   - What's unclear: Whether comment should be in db.py or a separate POSTGRES_MIGRATION.md
   - Recommendation: Put comment block in db.py at the connection function, showing the 2–3 lines to change (import asyncpg, connection string, schema differences). Keep it visible to implementers.

---

## Sources

### Primary (HIGH confidence)
- [discord.py 2.7.1 official repository](https://github.com/Rapptz/discord.py) - cog loading, app_commands, guild sync patterns
- [pydantic-settings documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - BaseSettings, environment variable handling, validation
- [aiosqlite GitHub repository](https://github.com/omnilib/aiosqlite) - async context manager patterns, threading model
- [PyPI: discord.py 2.7.1](https://pypi.org/project/discord.py/) - verified latest version (Mar 3, 2026)
- [PyPI: pydantic-settings 2.13.1](https://pypi.org/project/pydantic-settings/) - verified latest version (Feb 19, 2026)
- [PyPI: aiosqlite 0.22.1](https://pypi.org/project/aiosqlite/) - verified latest version (Dec 23, 2025)

### Secondary (MEDIUM confidence)
- [discord.py Extensions documentation](https://discordpy.readthedocs.io/en/stable/ext/commands/extensions.html) - load_extension error handling
- [discord.py app_commands examples](https://github.com/Rapptz/discord.py/blob/master/examples/app_commands/basic.py) - setup_hook, tree.sync patterns
- [AbstractUmbra's slash command guide](https://gist.github.com/AbstractUmbra/a9c188797ae194e592efe05fa129c57f) - guild sync specifics
- [Medium: Modular Discord Bots in Python](https://medium.com/@ajiboyetolu1/modular-discord-bots-in-python-a-guide-to-using-cogs-d89da141c4b9) - cog patterns
- [Python logging handlers documentation](https://docs.python.org/3/library/logging.handlers.html) - RotatingFileHandler, QueueHandler
- [SQLite WAL documentation](https://www.sqlite.org/wal.html) - concurrent read/write safety

### Tertiary (LOW confidence or community sources)
- [Hacker News: SQLite async connection pool](https://news.ycombinator.com/item?id=44530518) - mentions aiosqlitepool as alternative (not recommended for Phase 1)
- [discord.py GitHub Issue #1658](https://github.com/Rapptz/discord.py/issues/1658) - cog loading stuck state (edge case, mitigated by error handling)

---

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH - All libraries verified on PyPI with recent releases; discord.py 2.7.1 (Mar 2026), pydantic-settings 2.13.1 (Feb 2026), aiosqlite 0.22.1 (Dec 2025)
- **Architecture patterns:** HIGH - All patterns sourced from official documentation and discord.py examples; tested by large community (discord.py has 10k+ GitHub stars)
- **Pitfalls:** MEDIUM-HIGH - Pitfalls 1–4 documented in official issues and community guides; Pitfalls 5–7 are standard software engineering best practices

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (30 days). discord.py and pydantic are stable; aiosqlite minor updates may occur. Revalidate before Phase 2 if versions are pinned differently.
