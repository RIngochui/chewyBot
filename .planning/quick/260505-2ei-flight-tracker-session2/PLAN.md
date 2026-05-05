---
quick_id: 260505-2ei
slug: flight-tracker-session2
description: Flight tracker Session 2 — Serpapi Google Flights integration + poll command
created: 2026-05-05
---

# Flight Tracker — Session 2: Serpapi Integration

## Goal
Wire up live price fetching via Serpapi Google Flights engine.
End state: `python -m tracker poll <id>` fetches real prices and writes to price_snapshots.

## Tasks
- T1: Add SERPAPI_KEY to TrackerConfig (required, no default)
- T2: Add INSERT_PRICE_SNAPSHOT to queries.py
- T3: Create tracker/serpapi_client.py (search, parse, backoff)
- T4: Add `poll` command to cli.py
- T5: Commit
