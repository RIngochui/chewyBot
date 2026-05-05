---
quick_id: 260505-2lp
slug: flight-tracker-session3
status: complete
completed: 2026-05-05
commit: d0c9d77
---

# Summary

Built the polling daemon. `tracker run` polls all active routes on a schedule, saves snapshots, and logs threshold breaches. Tested one poll round live — CAD 901 on YYZ→LHR, no alert (above CAD 850 threshold, correct).

## Delivered
- TRACKER_POLL_INTERVAL_HOURS config var (default 4.0)
- SELECT_ALL_ACTIVE_ROUTES query
- tracker/scheduler.py: poll_all_routes(), _poll_route(), run_daemon()
- `run [--interval HOURS]` CLI command with Ctrl+C handling
