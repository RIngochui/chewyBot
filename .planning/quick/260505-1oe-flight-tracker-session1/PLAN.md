---
quick_id: 260505-1oe
slug: flight-tracker-session1
description: Flight tracker Session 1 — scaffold, config, SQLite schema, CLI
created: 2026-05-05
---

# Flight Tracker — Session 1 Scaffold

## Goal
Create the `tracker/` package alongside the existing bot with:
- TrackerConfig (pydantic-settings, tracker vars only)
- SQLite schema: routes, price_snapshots, alerts_sent
- Sync sqlite3 DB layer
- Click CLI: add, list, show, remove, pause, resume
- data/ and logs/ directories with .gitkeep

## Approved structure (confirmed by user)
```
tracker/
  __init__.py
  __main__.py
  cli.py
  config.py
  db.py
  queries.py
  models.py
  SPEC.md
data/.gitkeep
logs/.gitkeep
```

## Decisions captured
- Separate DB: data/tracker.db (sync sqlite3), not chewybot.db (async aiosqlite)
- TrackerConfig uses extra="ignore" — importable without bot env vars
- click (already installed 8.1.8), NOT typer
- logs/: *.log gitignore covers files; remove `logs/` directory entry so .gitkeep is tracked
- Logging: stdout (WARNING+) + RotatingFileHandler at logs/tracker.log (5MB × 3)
- Entry point: python -m tracker <command>
- No existing bot code touched

## Tasks

### T1 — Update .gitignore
Remove the `logs/` directory entry (*.log pattern already covers log files).

### T2 — Create directories
- data/.gitkeep
- logs/.gitkeep

### T3 — tracker/__init__.py
Empty package marker.

### T4 — tracker/__main__.py
Delegates to cli.cli().

### T5 — tracker/config.py
TrackerConfig(BaseSettings) with extra="ignore", TRACKER_DB_PATH and TRACKER_TIMEZONE only.

### T6 — tracker/queries.py
All SQL: CREATE_TABLES_SQL list + INSERT_ROUTE, SELECT_ALL_ROUTES, SELECT_ROUTE_BY_ID,
DELETE_ROUTE, UPDATE_ROUTE_ACTIVE constants.

### T7 — tracker/db.py
Sync sqlite3: _db_path(), init_db(), get_db() context manager. WAL + foreign keys.
Docstring must note the async/sync boundary rationale.

### T8 — tracker/models.py
Route dataclass with from_row() classmethod.

### T9 — tracker/cli.py
Click group + 6 commands (add, list, show, remove, pause, resume).
Input validation: IATA 3-letter uppercase, future dates, return > depart, positive threshold.

### T10 — tracker/SPEC.md
Multi-session plan skeleton. Note async/sync DB boundary explicitly.

### T11 — Update .env.example
Add TRACKER section with TRACKER_DB_PATH and TRACKER_TIMEZONE. Note Amadeus/webhook coming in later sessions.

### T12 — Update README.md
Add "## Flight Price Tracker" section with CLI usage. Update Project Structure tree.

### T13 — Commit
Atomic commit: all tracker scaffold files.
