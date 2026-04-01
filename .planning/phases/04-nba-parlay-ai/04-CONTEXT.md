# Phase 4 Context: NBA Parlay AI

## Phase
**Number:** 4
**Name:** NBA Parlay AI
**Goal:** The bot auto-posts a 3–5 leg NBA parlay daily at PARLAY_POST_TIME, learns from Discord reactions, persists weights across restarts, and filters underperforming leg types after 20+ tracked parlays

## Decisions

### A — leg_type taxonomy
**Decision:** Medium taxonomy — 6 leg types.

```
h2h_favorite    — moneyline, team is odds-on favorite
h2h_underdog    — moneyline, team is underdog
spread_home     — spread bet, home team covers
spread_away     — spread bet, away team covers
totals_over     — over/under, bet the over
totals_under    — over/under, bet the under
```

**Rationale:** At 1 parlay/day with 3–5 legs, ~30–50 leg samples/month. Broad enough to converge past the 20-parlay filter threshold; granular enough to learn something meaningful. Maps cleanly onto 5-factor model (home_away_split → spread_home/away, line_value → h2h_favorite/underdog).

**Architecture note:** Taxonomy is designed to extend — player prop types (`player_points_over`, `player_assists_under`, etc.) can be added as new rows in `leg_type_weights` when player stats legs are implemented.

---

### B — No-games fallback
**Decision:** Skip silently + log to LOG_CHANNEL_ID. No post to PARLAY_CHANNEL_ID.

**Triggers:**
- No NBA games scheduled that day
- Fewer than 3 scoreable legs found (after MIN_LEG_SCORE filter)

**Behavior:** Bot logs `"[Parlay] Skipped daily post — {reason}"` to LOG_CHANNEL_ID. PARLAY_CHANNEL_ID receives nothing.

---

### C — Confidence score formula
**Decision:** Weighted average incorporating learned leg_type weights.

```python
confidence = mean(leg_score * leg_type_weight for each leg) * 100
confidence = max(0, min(100, confidence))  # clamp to 0–100
```

**Rationale:** Only formula that makes the learning system visible in the embed. As weights improve from reactions, confidence scores become more accurate over time.

---

### D — Reaction scope
**Decision:** Any server member (non-bot), first valid ✅/❌ within 24 hours of posting wins.

**Rules:**
- Bot's own reactions are ignored (PAR-14)
- First valid reaction determines outcome — subsequent reactions on the same parlay are ignored
- Reactions after 24 hours are ignored
- Applies to both ✅ (HIT) and ❌ (MISS)

---

### E — balldontlie data depth
**Decision:** Full depth — `/games` + `/team_stats` endpoints.

**Endpoints used:**
- `/games` — recent game results (W/L), schedule (rest days), home/away game log
- `/team_stats` — season home/away splits for home_away_split factor

**Factor mapping:**
| Factor | Source |
|--------|--------|
| recent_form (0.25) | `/games` — last 5 game W/L |
| home_away_split (0.20) | `/team_stats` — season home/away win % |
| rest_days (0.15) | `/games` — days since last game |
| line_value (0.25) | Odds API (existing adapter) |
| historical_hit_rate (0.15) | `leg_type_weights` DB table |

**Mock mode:** Uses `mock/balldontlie_sample.json` (already exists).

---

## Deferred Ideas

- **Player prop legs** — e.g., "LeBron over 25.5 pts". Requires balldontlie `/player_stats` endpoint and new leg_type entries. Architecture supports this — add as a future phase.

---

## Canonical Refs

- `.planning/REQUIREMENTS.md` — PAR-01 through PAR-14
- `.planning/ROADMAP.md` — Phase 4 success criteria
- `cogs/arb.py` — Follow this pattern for background task + slash commands + embed builder
- `adapters/odds_api.py` — Reuse for NBA lines (existing adapter)
- `database/queries.py` — All SQL goes here, raw SQL only
- `mock/balldontlie_sample.json` — Mock data for MOCK_MODE
- `mock/odds_api_sample.json` — Existing mock odds data
- `services/arb_detector.py` — Pattern for service layer with tests
