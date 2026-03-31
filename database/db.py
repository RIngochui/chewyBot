"""
chewyBot async SQLite database layer.

Provides two public symbols:

  - init_db()   — Creates all 8 tables (idempotent), enables WAL mode, seeds
                  bot_config defaults.  Call once at bot startup.
  - get_db()    — Async context manager yielding an aiosqlite.Connection with
                  Row factory set.  Commits on clean exit, rolls back on error.

All SQL lives in database/queries.py — this file contains zero SQL string literals.
"""

import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from database.queries import CREATE_TABLES_SQL, UPSERT_BOT_CONFIG

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

DB_PATH: Path = Path("chewybot.db")


async def init_db(
    bankroll: float = 100.0,
    min_arb_pct: float = 0.5,
    min_ev_pct: float = 2.0,
    enabled_sports: str = "basketball_nba,americanfootball_nfl,icehockey_nhl",
) -> None:
    """Initialise the database: WAL mode, all 8 tables, and bot_config seed values.

    Safe to call on every startup — all CREATE TABLE statements use IF NOT EXISTS,
    and UPSERT_BOT_CONFIG uses ON CONFLICT DO NOTHING so existing values are never
    overwritten.

    Args:
        bankroll:       Starting bankroll value seeded into bot_config.
        min_arb_pct:    Minimum arbitrage percentage seeded into bot_config.
        min_ev_pct:     Minimum EV percentage seeded into bot_config.
        enabled_sports: Comma-separated sports list seeded into bot_config.
    """
    async with aiosqlite.connect(str(DB_PATH)) as db:
        # Enable WAL for concurrent read/write safety between scanner and cogs
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")

        # Create all 8 tables idempotently
        for statement in CREATE_TABLES_SQL:
            await db.execute(statement)

        # Seed bot_config defaults from environment-derived parameters.
        # ON CONFLICT DO NOTHING means existing operator-set values are preserved.
        defaults: list[tuple[str, str]] = [
            ("bankroll", str(bankroll)),
            ("min_arb_pct", str(min_arb_pct)),
            ("min_ev_pct", str(min_ev_pct)),
            ("enabled_sports", enabled_sports),
        ]
        for key, value in defaults:
            await db.execute(UPSERT_BOT_CONFIG, (key, value))

        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager that yields a database connection.

    Usage:
        async with get_db() as db:
            rows = await db.execute("SELECT ...")

    Commits on clean exit; rolls back and re-raises on any exception.
    Row factory is set to aiosqlite.Row for dict-like access by column name.
    """
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()
