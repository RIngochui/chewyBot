# Flight Tracker — Multi-Session Spec

## Architecture note: DB boundary

The Discord bot uses **aiosqlite** (async) against **`chewybot.db`** in the project root.
The tracker uses **plain sqlite3** (sync) against **`data/tracker.db`**.

These are intentionally separate in V1:
- Different files, different connection libraries, no shared state.
- The tracker runs as its own long-lived process outside the bot's asyncio event loop.
  Async SQLite would add complexity with zero benefit at this scale.
- If V2 ever needs read-only cross-process access (e.g., bot querying tracker alerts),
  SQLite's WAL mode supports concurrent readers safely.

---

## Session 1 — Scaffold + CLI ✓

**Deliverables:**
- `tracker/` package with `config.py`, `db.py`, `queries.py`, `models.py`, `cli.py`
- `TrackerConfig` (pydantic-settings, `extra='ignore'` — importable without bot vars)
- SQLite schema: `routes`, `price_snapshots`, `alerts_sent` + indexes
- Click CLI: `add`, `list`, `show`, `remove`, `pause`, `resume`
- `data/` and `logs/` directories with `.gitkeep`

**Entry point:** `python -m tracker <command>`

**Config vars added:**
- `TRACKER_DB_PATH` (default `data/tracker.db`)
- `TRACKER_TIMEZONE` (default `America/Toronto`)

---

## Session 2 — Amadeus API integration

_Plan TBD. Will add:_
- `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET` to `TrackerConfig`
- `tracker/amadeus.py` — OAuth2 token refresh + flight offers search
- Token caching (in-memory, refresh before expiry)
- Exponential backoff (max 3 retries) on 5xx / rate-limit responses
- Manual `python -m tracker poll <id>` command to test a single route

---

## Session 3 — Scheduler + polling loop

_Plan TBD. Will add:_
- `tracker/scheduler.py` — APScheduler or plain `asyncio` loop
- Per-route polling on configurable interval (e.g., every 4 hours)
- Price drop detection: compare cheapest snapshot to `absolute_threshold_cad`
- Write to `price_snapshots` and queue alerts
- `python -m tracker run` to start the daemon

---

## Session 4 — Discord webhook alerts

_Plan TBD. Will add:_
- `TRACKER_DISCORD_WEBHOOK_URL` to `TrackerConfig`
- `tracker/notifier.py` — format embed and POST to webhook
- `alerts_sent` row written after successful webhook post
- Deduplication: don't re-alert for same route + price within 24 h
- `tracker/SPEC.md` (this file) updated with actual decisions

---
