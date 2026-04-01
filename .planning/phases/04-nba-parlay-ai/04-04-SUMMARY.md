---
phase: 04-nba-parlay-ai
plan: "04"
subsystem: parlay-cog
tags: [parlay, discord, reactions, self-learning, sqlite, nba, feedback-loop]
dependency_graph:
  requires:
    - cogs/parlay.py (ParlayCog — existing from Plan 03)
    - database/queries.py (SELECT_PARLAY_BY_MESSAGE_ID, SELECT_PARLAY_LEGS, UPDATE_PARLAY_OUTCOME, SELECT_LEG_TYPE_WEIGHT, UPSERT_LEG_TYPE_WEIGHT_HIT, UPSERT_LEG_TYPE_WEIGHT_MISS)
    - database/db.py (get_db)
    - config.py (PARLAY_CHANNEL_ID, PARLAY_LEARNING_RATE)
  provides:
    - cogs/parlay.py — on_raw_reaction_add listener (self-learning reaction handler)
  affects:
    - leg_type_weights table (weights updated from Discord reactions)
    - parlays table (outcome field set from 'pending' to 'hit'/'miss')
tech_stack:
  added: []
  patterns:
    - commands.Cog.listener() for on_raw_reaction_add
    - discord.RawReactionActionEvent for payload-based reaction handling (works after restart)
    - DB-authoritative first-reaction-wins (outcome != 'pending' check — restart-safe)
    - Weight floor max(0.1, new_weight) to prevent weights reaching zero
key_files:
  created: []
  modified:
    - cogs/parlay.py
decisions:
  - "DB-authoritative first-reaction-wins check: outcome != 'pending' is restart-safe; no in-memory set needed"
  - "Both unicode (✅/❌) and name (white_check_mark/x) emoji variants handled per RESEARCH.md Pitfall 4"
  - "Weight floor at 0.1 (not 0.0) ensures weights never reach zero and leg types remain eligible for future parlays"
  - "Two separate get_db() contexts: first for read-only lookup, second for atomic write batch — avoids long-held cursor issues"
metrics:
  duration: "78 seconds"
  completed: "2026-04-01T03:39:17Z"
  tasks_completed: 1
  tasks_total: 2
  files_created: 0
  files_modified: 1
---

# Phase 04 Plan 04: Reaction Learning Handler Summary

**One-liner:** on_raw_reaction_add listener wired into ParlayCog — ✅/❌ reactions mark parlays hit/miss and update leg_type_weights via DB-authoritative, restart-safe first-reaction-wins logic.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add on_raw_reaction_add to ParlayCog | c7f9ad5 | cogs/parlay.py (modified) |

## What Was Built

### cogs/parlay.py — on_raw_reaction_add listener

**New imports added:**
- `timedelta` added to `from datetime import datetime, timedelta, timezone`
- `UPDATE_PARLAY_OUTCOME`, `SELECT_PARLAY_BY_MESSAGE_ID`, `SELECT_PARLAY_LEGS`, `SELECT_LEG_TYPE_WEIGHT`, `UPSERT_LEG_TYPE_WEIGHT_HIT`, `UPSERT_LEG_TYPE_WEIGHT_MISS` added to queries import block

**Listener: `on_raw_reaction_add`**

Implements the full PAR-06/PAR-07/PAR-14 feedback loop in 8 sequential guard steps:

1. **Bot guard (PAR-14):** `payload.member is None or payload.member.bot` → return immediately
2. **Channel scope:** `payload.channel_id != config.PARLAY_CHANNEL_ID` → return
3. **Emoji filter:** Checks both unicode (`✅`, `❌`) and Discord name variants (`white_check_mark`, `x`) per RESEARCH.md Pitfall 4
4. **Parlay lookup:** `SELECT_PARLAY_BY_MESSAGE_ID` — returns None if message not tracked
5. **First-reaction-wins (DB-authoritative):** `current_outcome != "pending"` → return. Restart-safe — no in-memory set needed
6. **24-hour window:** `datetime.now(tz=timezone.utc) - generated_at > timedelta(hours=24)` → return
7. **Outcome determination:** `outcome = "hit" if is_hit else "miss"`, `delta = +1 or -1`
8. **Atomic DB write:**
   - `UPDATE_PARLAY_OUTCOME` sets parlay outcome first (prevents race on rapid reactions)
   - For each leg: `SELECT_LEG_TYPE_WEIGHT` → compute `max(0.1, old + LEARNING_RATE * delta)` → `UPSERT_LEG_TYPE_WEIGHT_HIT` or `UPSERT_LEG_TYPE_WEIGHT_MISS`

## Checkpoint Awaiting Human Verification

Task 2 is a `checkpoint:human-verify` — paused awaiting smoke test confirmation.

**What to verify (9 steps):**
1. Start bot with MOCK_MODE=true: `python bot.py`
2. Confirm "chewyBot has logged in!" in LOG_CHANNEL_ID, no errors in chewybot.log
3. Run `/parlay` — confirm embed appears in PARLAY_CHANNEL_ID with title, 3-5 legs, combined odds, confidence score, footer with reaction prompt
4. React ✅ to the parlay message — confirm no error in logs
5. Run `/parlay_stats` — confirm total tracked, hit rate, leg type breakdown
6. Run `/parlay_history 3` — confirm recent parlays with outcomes
7. Run `/parlay` again — confirm reacted parlay shows as "hit" in history
8. Check SQLite: `sqlite3 chewybot.db "SELECT * FROM leg_type_weights;"` — confirm weights changed from 1.0
9. Restart bot — re-run `/parlay_stats` — confirm weights still updated (persisted)

## Deviations from Plan

None — plan executed exactly as written. The AST assertion in the plan's verify script used escaped double-quote syntax (`\"pending\"`) which matched the actual file content (`"pending"`).

## Known Stubs

None — the reaction handler is fully wired to real DB queries. All weight update logic, 24h window enforcement, and outcome recording are production-ready.

## Self-Check: PASSED

Files modified:
- /Users/ringochui/Projects/chewyBot/cogs/parlay.py — FOUND

Commits:
- c7f9ad5 — FOUND (feat(04-04): add on_raw_reaction_add reaction learning handler to ParlayCog)
