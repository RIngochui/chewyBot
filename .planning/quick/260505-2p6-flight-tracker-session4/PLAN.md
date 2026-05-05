---
quick_id: 260505-2p6
slug: flight-tracker-session4
description: Flight tracker Session 4 — Discord webhook alerts + deduplication
created: 2026-05-05
---

# Flight Tracker — Session 4: Discord Webhook Alerts

## Goal
When a threshold breach is detected, POST a Discord embed to the webhook URL,
write to alerts_sent, and suppress re-alerts for the same route within 24h.

## Tasks
- T1: Add TRACKER_DISCORD_WEBHOOK_URL (Optional[str]) to TrackerConfig
- T2: Add INSERT_ALERT_SENT + SELECT_RECENT_ALERT_FOR_ROUTE to queries.py
- T3: Create tracker/notifier.py (format embed, POST webhook, return message_id)
- T4: Rewrite _poll_route() in scheduler.py to call notifier + write alerts_sent + dedup
- T5: Update .env.example with TRACKER_DISCORD_WEBHOOK_URL
- T6: Commit
