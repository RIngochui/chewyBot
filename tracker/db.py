"""
Tracker synchronous SQLite layer.

Provides:
  - init_db()  — Creates all 3 tables and indexes. Idempotent.
  - get_db()   — Sync context manager yielding a sqlite3.Connection.

DB boundary note
────────────────
The Discord bot uses aiosqlite (async) against chewybot.db in the project root.
The tracker uses plain sqlite3 (sync) against data/tracker.db. They are
intentionally separate in V1: different files, different connection libraries,
no shared state. The tracker runs as its own process outside the bot's event
loop, so async is unnecessary complexity here.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from tracker.config import config
from tracker.queries import CREATE_TABLES_SQL

logger = logging.getLogger(__name__)


def _db_path() -> Path:
    """Resolve the DB path from config and ensure the parent directory exists."""
    path = Path(config.TRACKER_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db() -> None:
    """Create all tables and indexes. Safe to call on every startup.

    All statements use IF NOT EXISTS so this is fully idempotent — existing
    data is never touched.
    """
    path = _db_path()
    with sqlite3.connect(str(path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        for statement in CREATE_TABLES_SQL:
            conn.execute(statement)
        conn.commit()
    logger.debug("Tracker DB ready at %s", path)


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Sync context manager that yields a configured sqlite3 Connection.

    Usage:
        with get_db() as conn:
            rows = conn.execute("SELECT ...").fetchall()

    Commits on clean exit; rolls back and re-raises on any exception.
    Row factory is sqlite3.Row for column-name access.
    """
    path = _db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
