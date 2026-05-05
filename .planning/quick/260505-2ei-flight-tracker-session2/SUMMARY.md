---
quick_id: 260505-2ei
slug: flight-tracker-session2
status: complete
completed: 2026-05-05
commit: 6252c42
---

# Summary

Wired up Serpapi Google Flights and `tracker poll <id>`. Live tested against route #4 (YYZ→LHR), returned CAD 901.00 via Tap Air Portugal.

## Delivered
- `SERPAPI_KEY` added to TrackerConfig (required field)
- `tracker/serpapi_client.py`: `search()` with backoff, cabin/stops mapping, cheapest-offer parsing
- `INSERT_PRICE_SNAPSHOT` + `SELECT_RECENT_SNAPSHOTS` in queries.py
- `poll <id>` CLI command: fetches, saves snapshot, prints result; gracefully records failed polls
