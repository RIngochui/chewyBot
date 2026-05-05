---
quick_id: 260505-2lp
slug: flight-tracker-session3
description: Flight tracker Session 3 — polling daemon + threshold detection
created: 2026-05-05
---

# Flight Tracker — Session 3: Scheduler + Polling Loop

## Goal
`python -m tracker run` polls all active routes on a fixed interval,
saves snapshots, and logs threshold breaches. Discord alerts come in Session 4.

## Tasks
- T1: Add TRACKER_POLL_INTERVAL_HOURS to TrackerConfig (default 4.0)
- T2: Add SELECT_ALL_ACTIVE_ROUTES to queries.py
- T3: Create tracker/scheduler.py (poll_all_routes, _poll_route, run_daemon)
- T4: Add `run` command to cli.py + import config
- T5: Commit
