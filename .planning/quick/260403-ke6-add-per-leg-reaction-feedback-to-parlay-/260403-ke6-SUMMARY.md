---
phase: quick
plan: 260403-ke6
subsystem: parlay-ai
tags: [parlay, reactions, self-learning, sqlite, discord-py]
dependency_graph:
  requires: []
  provides: [per-leg-reaction-feedback]
  affects: [cogs/parlay.py, database/queries.py, utils/formatters.py]
tech_stack:
  added: []
  patterns: [DB-authoritative idempotency, 1-based leg index via emoji map, two-variant keycap Unicode]
key_files:
  created: []
  modified:
    - database/queries.py
    - utils/formatters.py
    - cogs/parlay.py
decisions:
  - _LEG_EMOJI_MAP uses 10 entries (2 Unicode variants per digit) to handle Discord's inconsistent keycap encoding
  - Branch A (whole-parlay) and Branch B (per-leg) are structurally independent within on_raw_reaction_add — no shared state between paths
  - Per-leg idempotency check uses outcome != 'pending' on the specific leg row, consistent with the whole-parlay first-reaction-wins pattern
metrics:
  duration: 18m
  completed: "2026-04-03T18:45:33Z"
  tasks_completed: 3
  files_modified: 3
---

# Quick Task 260403-ke6: Add Per-Leg Reaction Feedback to Parlay Summary

**One-liner:** Per-leg numbered emoji reactions (1️⃣-5️⃣) now mark individual parlay legs as "miss" and update only that leg's weight, enabling granular AI self-learning without requiring the whole parlay to miss.

## What Was Built

Extended the parlay AI's self-learning feedback loop with per-leg granularity:

1. **`database/queries.py`** — Added two SQL constants to the "Parlay persistence (Phase 4)" section:
   - `SELECT_PARLAY_LEGS_ORDERED`: fetches `id, leg_type, leg_score, outcome` ordered by `id ASC` so position maps reliably to leg index.
   - `UPDATE_PARLAY_LEG_OUTCOME`: single write path for individual leg outcomes (`UPDATE parlay_legs SET outcome = ? WHERE id = ?`).

2. **`utils/formatters.py`** — Updated `build_parlay_embed` footer from the old ✅/❌-only prompt to:
   `"React ✅ hit / ❌ miss — or 1️⃣-5️⃣ to mark which leg(s) failed!"`

3. **`cogs/parlay.py`** — Three additions:
   - `_NUMBER_EMOJIS` module-level constant (5-entry list) used in `_post_and_save_parlay` to add one numbered reaction per leg immediately after `channel.send`.
   - `_LEG_EMOJI_MAP` module-level constant (10 entries: 2 Unicode variants × 5 digits) for reliable keycap detection from Discord's `payload.emoji.name`.
   - `on_raw_reaction_add` restructured into two independent branches:
     - **Branch A (✅/❌)**: existing whole-parlay handler — logic unchanged, now explicitly `return`s.
     - **Branch B (number emoji)**: looks up parlay, enforces 24-hour window, fetches legs in insertion order, checks per-leg idempotency (`outcome != 'pending'`), marks target leg `"miss"`, updates only that leg's `leg_type_weights` weight.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add SQL queries for per-leg ordered fetch and outcome update | 6316c0c | database/queries.py |
| 2 | Update embed footer and add numbered reactions in _post_and_save_parlay | 0236f52 | utils/formatters.py, cogs/parlay.py |
| 3 | Handle per-leg emoji reactions in on_raw_reaction_add | 3095021 | cogs/parlay.py |

## Decisions Made

- **_LEG_EMOJI_MAP 10 entries**: Discord sends number keycap emoji as either `"1️⃣"` (with U+FE0F variation selector) or `"1\u20e3"` (bare combining enclosing keycap). Both variants are mapped to avoid silently ignoring valid reactions depending on Discord client version.
- **Two independent branches**: Kept Branch A and Branch B structurally separate (each does its own parlay lookup) rather than sharing the lookup step. This makes each branch self-contained and prevents any coupling that could break the existing ✅/❌ flow.
- **Per-leg idempotency**: Uses `target_leg["outcome"] != "pending"` — same DB-authoritative pattern as whole-parlay first-reaction-wins. No in-memory set needed; restart-safe.
- **Learning rate delta = -1 for leg miss**: Per-leg misses always count as miss (`PARLAY_LEARNING_RATE * -1`), consistent with how ❌ whole-parlay miss updates weights. No new config value needed.

## Verification

All automated checks passed:
```
SQL constants OK    — SELECT_PARLAY_LEGS_ORDERED, UPDATE_PARLAY_LEG_OUTCOME importable
footer import OK    — build_parlay_embed importable, footer updated
parse OK            — cogs/parlay.py AST parse clean
map OK (10 entries) — _LEG_EMOJI_MAP has 10 entries as required
```

Manual verification steps for operator:
- Post a parlay (`/parlay`) and confirm numbered reactions (1️⃣ through N️⃣) are auto-added matching leg count.
- React with 1️⃣ and verify: `SELECT id, outcome FROM parlay_legs WHERE parlay_id = <id>` shows first leg as "miss".
- React with 1️⃣ again; confirm `miss_count` in `leg_type_weights` did NOT increment again.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `database/queries.py` modified with SELECT_PARLAY_LEGS_ORDERED and UPDATE_PARLAY_LEG_OUTCOME: confirmed.
- `utils/formatters.py` footer updated: confirmed.
- `cogs/parlay.py` _LEG_EMOJI_MAP, _NUMBER_EMOJIS, restructured on_raw_reaction_add: confirmed.
- Commits exist: 6316c0c, 0236f52, 3095021 all verified in git log.
