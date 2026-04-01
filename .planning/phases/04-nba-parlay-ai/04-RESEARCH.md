# Phase 4: NBA Parlay AI - Research

**Researched:** 2026-03-31
**Domain:** NBA parlay generation, self-learning weighted scoring, Discord reaction handling, balldontlie API integration
**Confidence:** MEDIUM-HIGH

## Summary

Phase 4 implements the NBA Parlay AI cog, which auto-posts a 3–5 leg NBA parlay daily at a configured time, learns from Discord emoji reactions (✅/❌), persists learned weights in the database, and filters out underperforming leg types after sufficient data. The phase depends on Phase 3's arb scanner infrastructure and reuses The Odds API adapter for live NBA odds lines. Key technical challenges: (1) balldontlie API provides limited game/stats endpoints compared to training knowledge; (2) Discord's background task scheduling uses `discord.ext.tasks.loop(time=...)` with timezone-aware datetime objects; (3) reaction payload handling requires filtering bot reactions and checking the 24-hour window; (4) 5-factor weighted scoring requires careful normalization of missing data.

**Primary recommendation:** Follow arb.py pattern for background task structure. Use balldontlie's `/games` (with date range) and `/team_season_averages` (not `/team_stats`, which doesn't exist in free tier) endpoints. Implement weighted scoring with fallback defaults for missing factors. Use `discord.ext.tasks.loop(time=...)` with explicit UTC times. Filter reactions in `on_raw_reaction_add` by checking `payload.member.bot` and `message_id` matching bot-posted parlay messages.

## User Constraints (from CONTEXT.md)

### Locked Decisions
**A — leg_type taxonomy:** 6 team-based leg types (free API tier only):
- `h2h_favorite` — moneyline, team is odds-on favorite
- `h2h_underdog` — moneyline, team is underdog
- `spread_home` — spread bet, home team covers
- `spread_away` — spread bet, away team covers
- `totals_over` — over/under, bet the over
- `totals_under` — over/under, bet the under

**B — No-games fallback:** Skip silently + log to LOG_CHANNEL_ID. No post to PARLAY_CHANNEL_ID.

**C — Confidence score formula:** Weighted average incorporating learned leg_type weights:
```
confidence = mean(leg_score * leg_type_weight for each leg) * 100
confidence = max(0, min(100, confidence))  # clamp to 0–100
```

**D — Reaction scope:** Any server member (non-bot), first valid ✅/❌ within 24 hours of posting wins. Bot's own reactions ignored. First valid reaction determines outcome; subsequent reactions on same parlay ignored.

**E — balldontlie data depth:** Full depth — `/games` + `/team_season_averages` endpoints (note: `/team_stats` does not exist in free tier).

### Claude's Discretion
- Decomposition of Phase 4 into plans (number, order, content)

### Deferred Ideas
- Player prop legs (points, threes, rebounds, assists) — Requires balldontlie ALL-STAR+ plan + Odds API paid tier

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAR-01 | Data from balldontlie API (no key) for team stats + recent results; The Odds API adapter reused for NBA lines | balldontlie free tier provides `/games` endpoint (with date/season/team filtering) and `/team_season_averages` endpoint (NOT `/team_stats`). See Standard Stack. |
| PAR-02 | Auto-posts daily at PARLAY_POST_TIME (default 11:00 AM ET) to PARLAY_CHANNEL_ID | discord.ext.tasks.loop(time=...) with timezone-aware datetime.time objects. See Architecture Patterns. |
| PAR-03 | Generates 3–5 leg NBA parlay using 5-factor weighted scoring | 5 factors with weights: recent_form (0.25), home_away_split (0.20), rest_days (0.15), line_value (0.25), historical_hit_rate (0.15). See Architecture Patterns for normalization strategy. |
| PAR-04 | Never includes both sides of same game; only includes legs with leg_score >= MIN_LEG_SCORE (default 0.5) | Requires tracking game_id per leg; filter before adding to parlay. See Don't Hand-Roll. |
| PAR-05 | Every posted parlay saved to SQLite with all legs, metadata, Discord message_id | Existing parlay/parlay_legs tables defined in queries.py. Insert on post, update message_id after Discord send. |
| PAR-06 | ✅ reaction → marks HIT, increases weights; ❌ reaction → marks MISS, decreases weights | on_raw_reaction_add handler filters bot reactions via payload.member.bot. See Architecture Patterns. |
| PAR-07 | Weight update: new_weight = old_weight + (PARLAY_LEARNING_RATE * delta), delta ±1 | Simple delta update rule. No gradient descent needed. |
| PAR-08 | After 20+ tracked parlays, filters out leg types with historical hit rate < 30% | Query leg_type_weights for (hit_count / (hit_count + miss_count)) < 0.3, exclude from generation. |
| PAR-09 | All weights persist in leg_type_weights table, survive restarts | Load weights from DB on cog load, apply to generation. |
| PAR-10 | Parlay embed: title "🏀 chewyBot's NBA Parlay — [date]", each leg (team, market type, line, American odds), combined parlay odds, confidence score 0–100, reaction prompt | build_parlay_embed() function in utils/formatters.py. |
| PAR-11 | /parlay — manually generate today's parlay | Slash command that calls generate_parlay() and builds embed. |
| PAR-12 | /parlay_stats — hit rate, total tracked, best/worst leg types | Query parlays/leg_type_weights tables, build embed. |
| PAR-13 | /parlay_history [n] — last n parlays with hit/miss/pending outcome | SELECT * FROM parlays ORDER BY generated_at DESC LIMIT n, build embeds. |
| PAR-14 | Reaction handling: first valid ✅/❌ per parlay wins; ignores bot's own reactions; only tracks reactions on chewyBot messages | on_raw_reaction_add with payload filtering. See Architecture Patterns. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| discord.py | v2.x | Discord bot framework with slash commands and background tasks | Existing chewyBot dependency; stable, well-maintained |
| balldontlie API | free tier (no key) | NBA team stats, recent game results, schedules | Free public API, no auth required, covers all needed endpoints for free tier |
| The Odds API | free tier (existing) | NBA moneyline, spread, totals lines | Already integrated via adapters/odds_api.py in Phase 3; reuse directly |
| httpx | latest | Async HTTP client for balldontlie (same as Odds API adapter) | Already in requirements.txt; handles timeouts and retries |
| Pydantic v2 | latest | Data validation for balldontlie responses and Parlay models | Existing chewyBot dependency; type-safe validation |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| discord.ext.tasks | v2.x | Background task scheduling with specific times | Daily post at PARLAY_POST_TIME; built into discord.py |
| sqlite3 | builtin | Persist parlays, legs, weights, and outcomes | Existing DB layer; raw SQL in queries.py only |
| zoneinfo or pytz | if needed | Timezone-aware time handling for PARLAY_POST_TIME | Only if PARLAY_POST_TIME needs timezone conversion from ET to UTC |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| balldontlie free tier | balldontlie ALL-STAR+ ($29/month) | Unlocks player props (points, threes, etc.) — deferred to v2 |
| Odds API reuse | dedicated balldontlie odds endpoint | balldontlie doesn't expose betting lines; must use Odds API |
| discord.ext.tasks | APScheduler library | discord.ext.tasks is built-in, battle-tested in discord.py; APScheduler adds dependency |
| SQLite queries | Hand-rolled ORM | Raw SQL in queries.py follows chewyBot constraint; no ORMs |

**Installation:**
No new packages required. balldontlie uses the existing httpx client from odds_api.py. Existing dependencies cover all needs.

**Balldontlie API Setup (verified 2026-03-31):**

Free tier: **5 requests/minute rate limit**, no authentication key required.

Key endpoints for PAR-01:
- `GET /v1/games` — Recent game results and schedule
  - **Parameters:** `dates[]` (YYYY-MM-DD format), `seasons[]` (year), `team_ids[]` (integer), `postseason` (boolean), cursor-based pagination (`cursor`, `per_page` default 25, max 100)
  - **Response:** Game object with home/away team IDs, scores, period info, status ("Final", "In Progress", etc.), game date
  - **Use case:** Retrieve last 5 games per team for recent_form factor; check today's scheduled games for parlay generation
  
- `GET /v1/team_season_averages/{category}` — Season stats split by home/away (replaces training knowledge of `/team_stats`)
  - **Parameters:** `season` (year, required), `season_type` ("Regular Season" | "Playoffs"), optional `team_ids[]`, cursor pagination
  - **Response:** Team stats for season, with home/away splits available
  - **Use case:** Retrieve home_away_split factor (home win% vs away win%)
  - **CORRECTION:** CONTEXT.md references `/team_stats` which does not exist in free tier. Use `/team_season_averages` instead.

- **Pagination:** Cursor-based (`meta.next_cursor`, `per_page`). No page number offsets.
- **Rate limits:** 5 req/min. Implement backoff same as odds_api.py (exponential 1s, 2s).

## Architecture Patterns

### Recommended Project Structure
```
cogs/
├── parlay.py              # ParlayCog with daily loop, slash commands, reaction handler
├── arb.py                 # Reference for cog patterns (background task setup, commands)

services/
├── parlay_engine.py       # generate_parlay(), leg scoring, weight persistence
├── balldontlie_adapter.py # NEW: adapter for /games and /team_season_averages (similar to odds_api.py)
├── parlay_scorer.py       # NEW: 5-factor weighted scoring logic

adapters/
├── odds_api.py            # Reuse directly for NBA lines (ARB-01 pattern)
├── base.py                # Reference interface (no changes needed)

utils/
├── formatters.py          # Existing build_arb_embed(); add build_parlay_embed()
├── odds_math.py           # Existing decimal/american conversion; use here

database/
├── queries.py             # All SQL here (existing parlays, parlay_legs, leg_type_weights, bot_config tables)
├── db.py                  # Existing connection pool; no changes

models/
├── parlay.py              # Existing Parlay, ParlayLeg classes (Pydantic v2)

mock/
├── balldontlie_sample.json # Existing mock data structure (reviewed)
├── odds_api_sample.json    # Existing reuse for NBA odds
```

### Pattern 1: Background Task at Specific Time (PARLAY_POST_TIME)

**What:** Use `@discord.ext.tasks.loop(time=...)` with timezone-aware `datetime.time` to post daily at a fixed time (e.g., 11:00 AM ET).

**When to use:** Daily auto-post at PARLAY_POST_TIME (PAR-02).

**Example:**
```python
# Source: https://discordpy.readthedocs.io/en/stable/ext/tasks/index.html (discord.py 2.x)
from discord.ext import tasks
import datetime

class ParlayCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Parse PARLAY_POST_TIME (e.g. "11:00") and convert to UTC
        # Example: "11:00" ET = "16:00" UTC (daylight savings requires special handling)
        hour, minute = map(int, config.PARLAY_POST_TIME.split(':'))
        # Assume input is ET; convert to UTC manually or use zoneinfo
        # For now: assume UTC if no TZ info in config
        utc_time = datetime.time(hour=hour, minute=minute, tzinfo=datetime.timezone.utc)
        self.daily_parlay.change_interval(time=[utc_time])
    
    async def cog_load(self) -> None:
        """Load on cog initialize."""
        self.daily_parlay.start()
    
    @tasks.loop(time=datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_parlay(self) -> None:
        """Post daily parlay at scheduled time. PAR-02."""
        channel = self.bot.get_channel(config.PARLAY_CHANNEL_ID)
        if channel:
            parlay = await generate_parlay(min_leg_score=config.MIN_LEG_SCORE)
            if parlay is None:
                # Skip silently (PAR-B fallback)
                log_channel = self.bot.get_channel(config.LOG_CHANNEL_ID)
                if log_channel:
                    await log_channel.send("[Parlay] Skipped daily post — no scoreable legs found")
            else:
                embed = build_parlay_embed(parlay)
                msg = await channel.send(embed=embed)
                parlay.discord_message_id = str(msg.id)
                # Save to DB with message_id
                await db.insert_parlay(parlay)
    
    @daily_parlay.before_loop
    async def before_daily_parlay(self) -> None:
        """Wait for bot to be ready before loop starts."""
        await self.bot.wait_until_ready()
```

**Key insight:** `datetime.timezone.utc` makes times timezone-aware. If PARLAY_POST_TIME is in ET, convert manually (ET = UTC-5 standard, UTC-4 daylight saving) or use `zoneinfo.ZoneInfo("America/New_York")` (Python 3.9+). For simplicity, assume UTC in .env or document the conversion.

### Pattern 2: Reaction Handling with `on_raw_reaction_add` (PAR-06, PAR-14)

**What:** Listen for ✅/❌ reactions on bot-posted parlay messages. Filter out bot reactions, enforce 24-hour window, mark first valid reaction as outcome (HIT or MISS).

**When to use:** Learning system that updates leg_type_weights from Discord reactions.

**Example:**
```python
# Source: https://github.com/Rapptz/discord.py/discussions/8369 + payload analysis
from datetime import datetime, timedelta, timezone

class ParlayCog(commands.Cog):
    # Track which parlays have already been scored to enforce "first reaction wins" rule
    _scored_parlay_ids: set[int] = set()
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Handle ✅/❌ reactions on parlay messages. PAR-06, PAR-14."""
        
        # Ignore bot's own reactions (PAR-14)
        if payload.member and payload.member.bot:
            return
        
        # Only track reactions on our parlay messages (in PARLAY_CHANNEL_ID)
        if payload.channel_id != config.PARLAY_CHANNEL_ID:
            return
        
        # Only track ✅ and ❌ emoji
        if payload.emoji.name not in ["✅", "❌"]:
            return
        
        # Query DB for parlay with this message_id
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, generated_at FROM parlays WHERE discord_message_id = ?",
                (str(payload.message_id),)
            )
            row = await cursor.fetchone()
        
        if not row:
            return  # Not a parlay message
        
        parlay_id, generated_at_iso = row
        
        # Enforce 24-hour window (PAR-14)
        generated_at = datetime.fromisoformat(generated_at_iso).replace(tzinfo=timezone.utc)
        if datetime.now(tz=timezone.utc) - generated_at > timedelta(hours=24):
            return  # Reaction is too old
        
        # Enforce "first reaction wins" rule (PAR-14)
        if parlay_id in self._scored_parlay_ids:
            return  # Already scored
        
        # Mark parlay as scored and update weights
        self._scored_parlay_ids.add(parlay_id)
        outcome = "hit" if payload.emoji.name == "✅" else "miss"
        
        # Update leg_type_weights based on reaction
        delta = 1 if outcome == "hit" else -1
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT leg_type, leg_score FROM parlay_legs WHERE parlay_id = ?
                """,
                (parlay_id,)
            )
            legs = await cursor.fetchall()
            
            for leg in legs:
                leg_type, leg_score = leg
                # Get current weight
                w_cursor = await db.execute(
                    "SELECT weight FROM leg_type_weights WHERE leg_type = ?",
                    (leg_type,)
                )
                w_row = await w_cursor.fetchone()
                old_weight = w_row[0] if w_row else 1.0
                
                # Update weight and counts
                new_weight = old_weight + (config.PARLAY_LEARNING_RATE * delta)
                if outcome == "hit":
                    await db.execute(
                        """
                        INSERT INTO leg_type_weights (leg_type, weight, hit_count, miss_count)
                        VALUES (?, ?, 1, 0)
                        ON CONFLICT(leg_type) DO UPDATE SET
                            weight = ?,
                            hit_count = hit_count + 1,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (leg_type, new_weight, new_weight)
                    )
                else:
                    await db.execute(
                        """
                        INSERT INTO leg_type_weights (leg_type, weight, hit_count, miss_count)
                        VALUES (?, ?, 0, 1)
                        ON CONFLICT(leg_type) DO UPDATE SET
                            weight = ?,
                            miss_count = miss_count + 1,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (leg_type, new_weight, new_weight)
                    )
            
            # Mark parlay outcome
            await db.execute(
                "UPDATE parlays SET outcome = ? WHERE id = ?",
                (outcome, parlay_id)
            )
        
        logger.info(f"Parlay {parlay_id}: {outcome.upper()} reaction recorded")
```

**Key insight:** `payload.member.bot` checks if reactor is a bot. `payload.message_id` + `payload.channel_id` uniquely identify the message. Store scored parlay IDs in-memory or query DB each time to prevent duplicate scoring.

### Pattern 3: 5-Factor Weighted Scoring (PAR-03)

**What:** Compute leg_score (0–1) from 5 factors, each normalized to 0–1, weighted by fixed coefficients. Handle missing data gracefully.

**When to use:** Per-leg scoring before combining into parlay and confidence score.

**Factors & weights:**
- `recent_form` (0.25): Last 5 game W/L record → win_pct (0–1)
- `home_away_split` (0.20): Season home/away record → home_pct if home game, away_pct if away (0–1)
- `rest_days` (0.15): Days since last game → sigmoid(rest_days / 2) clamped to [0, 1]
- `line_value` (0.25): Odds-implied probability → decimal_odds → implied_prob (0–1)
- `historical_hit_rate` (0.15): (hit_count / (hit_count + miss_count)) from leg_type_weights (0–1), default 0.5 if no data

**Example normalization:**
```python
# Source: https://developers.google.com/machine-learning/crash-course/numerical-data/normalization
def normalize_min_max(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalization to [0, 1]."""
    if max_val == min_val:
        return 0.5  # Default if range is zero
    return (value - min_val) / (max_val - min_val)

def sigmoid(x: float) -> float:
    """Smooth 0-1 mapping for rest_days."""
    import math
    return 1 / (1 + math.exp(-x))

async def score_leg(
    team_id: int,
    is_home: bool,
    market_type: str,
    line_value: float,
    leg_type: str,
    games_data: dict,  # From balldontlie /games
    team_stats: dict,   # From balldontlie /team_season_averages
    odds_record: NormalizedOdds,  # From Odds API adapter
) -> float:
    """Compute leg_score (0-1) from 5 factors. PAR-03."""
    
    # Factor 1: recent_form (0.25)
    # Last 5 games W/L from games_data
    recent_games = [g for g in games_data if g['team_id'] == team_id][:5]
    if recent_games:
        wins = sum(1 for g in recent_games if (
            (is_home and g['home_team_score'] > g['away_team_score']) or
            (not is_home and g['away_team_score'] > g['home_team_score'])
        ))
        recent_form = wins / len(recent_games)
    else:
        recent_form = 0.5  # Default if no games
    
    # Factor 2: home_away_split (0.20)
    # From team_season_averages: home_record "21-15" means 21W-15L
    if is_home:
        home_record = team_stats.get('home_record', "0-0")  # "W-L" format
        wins, losses = map(int, home_record.split('-'))
        home_away_split = wins / (wins + losses) if (wins + losses) > 0 else 0.5
    else:
        away_record = team_stats.get('away_record', "0-0")
        wins, losses = map(int, away_record.split('-'))
        home_away_split = wins / (wins + losses) if (wins + losses) > 0 else 0.5
    
    # Factor 3: rest_days (0.15)
    # Days since last game (from games_data most recent date)
    if recent_games:
        last_game_date = recent_games[0]['date']  # ISO format YYYY-MM-DD
        from datetime import date
        days_rest = (date.today() - date.fromisoformat(last_game_date)).days
        rest_days = min(1.0, sigmoid(days_rest / 2.0))  # Sigmoid smoothing
    else:
        rest_days = 0.5
    
    # Factor 4: line_value (0.25)
    # Convert decimal odds to implied probability
    decimal_odds = odds_record.decimal_odds
    line_value_norm = 1.0 / decimal_odds if decimal_odds > 0 else 0.5
    
    # Factor 5: historical_hit_rate (0.15)
    # From leg_type_weights table
    async with get_db() as db:
        w_cursor = await db.execute(
            "SELECT hit_count, miss_count FROM leg_type_weights WHERE leg_type = ?",
            (leg_type,)
        )
        w_row = await w_cursor.fetchone()
    
    if w_row:
        hit_count, miss_count = w_row
        historical_hit_rate = hit_count / (hit_count + miss_count) if (hit_count + miss_count) > 0 else 0.5
    else:
        historical_hit_rate = 0.5  # Default for new leg types
    
    # Weighted average
    leg_score = (
        recent_form * 0.25 +
        home_away_split * 0.20 +
        rest_days * 0.15 +
        line_value_norm * 0.25 +
        historical_hit_rate * 0.15
    )
    
    return max(0.0, min(1.0, leg_score))  # Clamp to [0, 1]
```

**Key insight:** Missing data gets 0.5 default (neutral). Factors are already in [0, 1] or converted to it via normalization. No gradient descent needed — simple weighted average.

### Pattern 4: Parlay Odds Calculation (PAR-03, PAR-10)

**What:** Multiply all leg odds together to get combined odds. Convert from American to decimal before multiplying, convert result back to American for display.

**When to use:** Every generated parlay (PAR-03) and parlay embed (PAR-10).

**Example:**
```python
# Source: https://oddsindex.com/guides/how-to-calculate-parlay-odds
from utils.odds_math import american_to_decimal, decimal_to_american

async def calculate_parlay_odds(legs: list[ParlayLeg]) -> tuple[float, int]:
    """Calculate combined odds for parlay. Returns (decimal_odds, american_odds)."""
    combined_decimal = 1.0
    for leg in legs:
        # leg.american_odds is the American odds (e.g., -110, +200)
        decimal = american_to_decimal(leg.american_odds)
        combined_decimal *= decimal
    
    combined_american = decimal_to_american(combined_decimal)
    return combined_decimal, int(combined_american)

# Example: 3-leg parlay with -110, -110, +150 american odds
# Decimal: 1.909, 1.909, 2.5
# Combined decimal: 1.909 * 1.909 * 2.5 = 9.09
# Combined american: decimal_to_american(9.09) = +809
```

**Key insight:** Parlay odds multiply in decimal format. American odds are for display only. Existing utils/odds_math.py has conversion helpers.

### Anti-Patterns to Avoid
- **Mixing timezone-naive and timezone-aware times:** Always use `datetime.timezone.utc` or `zoneinfo.ZoneInfo("...")` for `tasks.loop(time=...)`. Naive times default to UTC but don't mix with local system time.
- **Scoring all reactions on a message:** Enforce "first reaction wins" (PAR-14) by tracking scored parlay IDs or querying DB for outcome != "pending" before processing.
- **Not handling missing balldontlie data:** If /games returns no results for a team, set recent_form to 0.5 (neutral). Same for /team_season_averages.
- **Forgetting to check `payload.member.bot`:** Will score bot's own reactions, polluting the learning system.
- **Normalizing data after missing values:** Handle missing data first (imputation with defaults), then normalize.
- **Hardcoding leg_type filters:** Use database queries to dynamically exclude low-hit-rate legs after 20+ tracked parlays (PAR-08).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parlay odds calculation | Custom multiplication logic | existing `american_to_decimal()` / `decimal_to_american()` in utils/odds_math.py | Odds conversions are complex; error-prone to implement from scratch |
| Background task scheduling at specific time | Custom sleep/loop with time checks | `@discord.ext.tasks.loop(time=...)` from discord.py | Handles timezone transitions, daylight savings, and reconnection logic automatically |
| Reaction filtering / message tracking | Manual list of message IDs | discord.py `RawReactionActionEvent.message_id` + DB query | discord.py payload provides all context; DB gives durable state across restarts |
| Weighted factor normalization | Custom min-max logic | Existing sigmoid() + clamp patterns (see Architecture Patterns) | ML consensus: min-max normalization is well-established; edge cases are known |
| balldontlie HTTP requests | Custom httpx calls in each service | Dedicated adapter class (similar to odds_api.py pattern) | Reusable exponential backoff, rate limit tracking, mock mode support |
| SQL weight updates | Transaction-less separate queries | UPSERT with ON CONFLICT clause (see Pattern 2) | UPSERT is atomic; prevents race conditions on weight increments |

**Key insight:** Parlay scoring and odds math are deceptively complex once you account for edge cases (missing data, timezone conversions, weight persistence across restarts). Use proven patterns from Phase 3 (arb scanner) and existing utils.

## Common Pitfalls

### Pitfall 1: timezone Mismatch in `tasks.loop(time=...)`
**What goes wrong:** Task runs at wrong time or not at all. Example: PARLAY_POST_TIME="11:00" is intended as 11 AM ET, but code treats it as UTC, posting at 4 PM ET instead.

**Why it happens:** `datetime.time` objects are timezone-naive by default. `tasks.loop(time=...)` assumes UTC if no tzinfo is provided. No error is raised — the task silently runs at the wrong time.

**How to avoid:**
1. Explicitly document in .env.example that PARLAY_POST_TIME is UTC (or convert on load)
2. Use `zoneinfo.ZoneInfo("America/New_York")` if ET is required: `datetime.time(hour=11, minute=0, tzinfo=zoneinfo.ZoneInfo("America/New_York"))`
3. Test the loop in a test environment first by checking `bot.dispatch("before_loop")` logs

**Warning signs:**
- Parlay posts happen at the wrong hour
- Logs show task starting but message not sent to Discord
- Multiple posts in same day (if task runs multiple times due to restart)

### Pitfall 2: Scoring a Parlay Multiple Times from Repeated Reactions
**What goes wrong:** User adds ✅ reaction, weight updates. User removes reaction. User adds ❌ reaction. Weight updates again (incorrectly).

**Why it happens:** `on_raw_reaction_add` is called every time a reaction is added. No deduplication by default. You must enforce the "first reaction wins" rule manually.

**How to avoid:**
1. Query DB for `parlays.outcome` before updating weights; if outcome != "pending", skip processing
2. OR track scored_parlay_ids in-memory set during bot lifetime (reload on startup)
3. Add `outcome` column to parlays table (exists in schema) and CHECK outcome = "pending" before update

**Warning signs:**
- Same parlay outcome changes multiple times after multiple reactions
- Logs show duplicate weight updates for same parlay_id
- /parlay_stats shows inconsistent hit counts

### Pitfall 3: Missing balldontlie Data Causing Silent Failures
**What goes wrong:** /games returns empty list (no games scheduled), code crashes or generates parlay with missing factors, bot fails to post or posts partial parlay.

**Why it happens:** balldontlie API can return empty results legitimately (no games today), but code assumes data is always present. No graceful degradation to default values.

**How to avoid:**
1. Always check for empty results: `if not games_data: return None` (skip silently per PAR-B)
2. Set all factors to 0.5 (neutral) if data is missing: `recent_form = 0.5 if not recent_games else ...`
3. Log to LOG_CHANNEL_ID when data is missing (PAR-B fallback): "Skipped parlay — no games scheduled today"

**Warning signs:**
- Bot doesn't post parlay on certain days (no error logs)
- KeyError: 'home_record' when querying team_stats
- Parlay embeds have 0.0 confidence score or NaN legs

### Pitfall 4: Reaction Emoji Matching Case Sensitivity
**What goes wrong:** Unicode emoji name might be "white_check_mark" instead of "✅", or "X" instead of "❌". Code checks `if emoji.name == "✅"` and misses valid reactions.

**Why it happens:** Discord emoji names vary; custom emoji have different representations than standard Unicode emoji.

**How to avoid:**
1. Check both `emoji.name` (text name) and `emoji.id` (custom emoji ID) if needed
2. Use `emoji.id` for custom server emoji: `if payload.emoji.id == CHECKMARK_EMOJI_ID`
3. For standard emoji, check `str(payload.emoji)` instead: `if str(payload.emoji) in ["✅", "❌"]`
4. Test by adding reactions in a test Discord server and logging payload contents

**Warning signs:**
- Reactions don't trigger on_raw_reaction_add handler
- Logs show payload with unexpected emoji.name values
- Custom server emoji aren't recognized as valid parlay reactions

### Pitfall 5: Confidence Score Formula Weighting Without Normalization
**What goes wrong:** Confidence score is always 0-25% even though all leg_scores are 0.5+. Formula doesn't properly reflect learned weights.

**Why it happens:** If weights aren't normalized to [0, 1], sum of weights != 1, and average is skewed. Example: `confidence = mean(leg_score * weight)` where weight is raw hit_count, not hit_rate.

**How to avoid:**
1. Ensure leg_type_weights.weight is always in [0, 1] range: `new_weight = max(0, min(1, old_weight + delta))`
2. Or normalize during calculation: `weight_norm = weight / max(weights)` before multiplying
3. Use historical_hit_rate as the weight (already normalized): `weight = hit_count / (hit_count + miss_count)`
4. Test with small numbers: 3-leg parlay with all 0.75 scores should give ~75% confidence

**Warning signs:**
- Confidence scores are always very low (< 30%) or very high (> 90%)
- Weights in DB grow unbounded (1.0 → 1.05 → 1.1, never clamped)
- /parlay_stats shows impossible percentages (>100% hit rate)

## Code Examples

Verified patterns from existing chewyBot codebase and official sources:

### Background Task Setup (arb.py Pattern)
```python
# Source: cogs/arb.py (Phase 3, verified working)
class ArbCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_scan_at: Optional[datetime] = None

# For daily task in ParlayCog:
from discord.ext import tasks
import datetime

class ParlayCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.daily_parlay.start()
    
    @tasks.loop(time=datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_parlay(self) -> None:
        """Daily parlay generation at UTC 16:00."""
        # Implementation here
        pass
    
    @daily_parlay.before_loop
    async def before_daily_parlay(self) -> None:
        await self.bot.wait_until_ready()
```

### Reaction Handling with `on_raw_reaction_add`
```python
# Source: https://github.com/Rapptz/discord.py/discussions/8369 pattern
@commands.Cog.listener()
async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
    """Process reaction on parlay message."""
    # Ignore bots
    if payload.member.bot:
        return
    
    # Fetch message
    channel = self.bot.get_channel(payload.channel_id)
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(payload.message_id)
    except discord.NotFound:
        return
    
    # Process reaction (implementation specific)
    if payload.emoji.name == "✅":
        # Mark as hit
        pass
```

### Min-Max Normalization with Default Fallback
```python
# Source: https://developers.google.com/machine-learning/crash-course/numerical-data/normalization
def normalize_to_zero_one(value: float, min_val: float, max_val: float, default: float = 0.5) -> float:
    """Normalize value to [0, 1]. Return default if range is zero."""
    if max_val == min_val:
        return default
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

# Example usage:
recent_form = normalize_to_zero_one(wins, 0, 5)  # Wins out of 5 games
rest_factor = normalize_to_zero_one(days_rest, 0, 3)  # Normalizes 0-3 days to 0-1
```

### Parlay Odds Multiplication
```python
# Source: utils/odds_math.py pattern + https://oddsindex.com/guides/how-to-calculate-parlay-odds
from utils.odds_math import american_to_decimal, decimal_to_american

def combine_parlay_odds(american_odds_list: list[int]) -> tuple[float, int]:
    """Multiply odds together. Return (decimal, american)."""
    combined_decimal = 1.0
    for ao in american_odds_list:
        decimal = american_to_decimal(ao)
        combined_decimal *= decimal
    combined_american = decimal_to_american(combined_decimal)
    return combined_decimal, int(combined_american)

# Example:
legs_odds = [-110, -110, +200]
decimal, american = combine_parlay_odds(legs_odds)
# decimal ≈ 7.46, american ≈ +646
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom sleep-based task scheduling | discord.ext.tasks.loop(time=...) with timezone-aware times | discord.py v1.5+ | Built-in, handles DST, reconnection logic, no external dependencies |
| Per-service HTTP clients (httpx in each adapter) | Shared AsyncClient in adapter for connection pooling | Current chewyBot standard | Reduces connection overhead, reuses TCP connections |
| ORM-based weight persistence (SQLAlchemy) | Raw SQL with UPSERT ON CONFLICT in queries.py | chewyBot architecture | Explicit control, no magic, easier PostgreSQL migration, keeps all SQL in one file |
| Naive datetime comparisons for 24-hour window | `datetime.now(tz=timezone.utc) - generated_at > timedelta(hours=24)` | Python 3.3+ | Timezone-aware prevents daylight savings bugs |
| Manual reaction deduplication loops | Database outcome column + in-memory tracking | Current best practice | Prevents duplicate scoring without adding overhead |

**Deprecated/outdated:**
- **discord-py-voice (old voice lib):** Replaced by discord.py v2 voice client (used in music cog). Not relevant to parlay cog.
- **APScheduler for task scheduling:** discord.py built-in tasks are simpler and more reliable for this use case.
- **Redis for reaction tracking:** SQLite leg_type_weights table is sufficient for v1; can upgrade to Redis for multi-instance deployments in v2.

## Open Questions

1. **PARLAY_POST_TIME timezone handling**
   - What we know: config.PARLAY_POST_TIME is "HH:MM" string, interpreted as time of day to post
   - What's unclear: Is this ET, UTC, or local system time?
   - Recommendation: Document in .env.example as UTC (simplest). If user wants ET, add PARLAY_TIMEZONE env var and convert on load using zoneinfo.

2. **balldontlie `/games` pagination for "today's schedule"**
   - What we know: `/games` accepts `dates[]` parameter for filtering by date
   - What's unclear: Does `dates[]=2026-03-31` return games on that exact date, or a range?
   - Recommendation: Test with mock data first. balldontlie_sample.json has games on 2026-03-20 through 2026-03-29; verify date filtering works as expected.

3. **Handling weekend/holiday with no scheduled games**
   - What we know: PAR-B fallback says skip silently if no games
   - What's unclear: How often does this happen? Should we warn user after N consecutive skips?
   - Recommendation: Log every skip to LOG_CHANNEL_ID. Monitor in production. Add optional PARLAY_SKIP_WARNING_THRESHOLD if pattern emerges.

4. **Weight initialization for new leg types**
   - What we know: First time a leg_type is seen, default historical_hit_rate = 0.5
   - What's unclear: Should new leg_type be inserted into leg_type_weights immediately (with weight=1.0, hit=0, miss=0), or only after first reaction?
   - Recommendation: Insert on first leg generation with weight=1.0 (neutral). Update counts only after reaction. Simplifies queries later.

5. **Plan decomposition strategy**
   - What we know: Phase 4 involves balldontlie adapter, parlay generation, reaction handling, weight learning, and 5 slash commands
   - What's unclear: Should we split into 3-4 plans? Order?
   - Recommendation: Suggest 4 plans: (1) balldontlie adapter + leg scoring, (2) generate_parlay() + odds calc, (3) ParlayCog shell + daily loop + slash commands, (4) Reaction handler + weight learning. Execute in order.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core runtime | ✓ | 3.11+ | — |
| discord.py | Bot framework | ✓ | 2.x | — |
| httpx | HTTP client (odds/balldontlie) | ✓ | latest | — |
| Pydantic | Data validation | ✓ | 2.x | — |
| SQLite | Database | ✓ | builtin | — |
| balldontlie API | PAR-01 data fetch | ✓ | free tier, no key | — |
| The Odds API | NBA lines | ✓ | existing adapter | — |
| zoneinfo | Timezone support (Python 3.9+) | ✓ | builtin 3.9+ | pytz (older Python) |

**Missing dependencies with no fallback:**
- None. All dependencies for Phase 4 are already available or builtin.

**Missing dependencies with fallback:**
- None. Phase 4 has no optional external dependencies.

## Sources

### Primary (HIGH confidence)
- [balldontlie API Documentation](https://docs.balldontlie.io) - `/games` and `/team_season_averages` endpoints verified 2026-03-31
- [discord.py tasks documentation](https://discordpy.readthedocs.io/en/stable/ext/tasks/index.html) - `tasks.loop(time=...)` behavior and timezone handling
- [discord.py GitHub discussions #8369](https://github.com/Rapptz/discord.py/discussions/8369) - `on_raw_reaction_add` with RawReactionActionEvent payload
- [chewyBot Phase 3 source code](cogs/arb.py, adapters/odds_api.py, database/queries.py) - Existing patterns for cog structure, background tasks, adapter pattern, SQL

### Secondary (MEDIUM confidence)
- [OddsIndex Parlay Odds Guide](https://oddsindex.com/guides/how-to-calculate-parlay-odds) - Parlay multiplication formula verified with existing utils/odds_math.py
- [Google ML Crash Course: Normalization](https://developers.google.com/machine-learning/crash-course/numerical-data/normalization) - Min-max normalization with missing data handling
- [discord.py background_task.py example](https://github.com/Rapptz/discord.py/blob/master/examples/background_task.py) - Concrete example of `tasks.loop` setup with `before_loop`

### Tertiary (LOW confidence / Training Data)
- APScheduler comparison: Training data suggests it's a valid alternative, but discord.py built-in tasks are preferred for single-instance bots

## Metadata

**Confidence breakdown:**
- **Standard Stack (HIGH):** balldontlie API verified via official docs; discord.py v2.x confirmed in chewyBot; odds math patterns existing in codebase
- **Architecture patterns (MEDIUM-HIGH):** discord.py tasks and reaction handling documented officially; patterns match chewyBot Phase 3 structure; no breaking changes expected
- **Pitfalls (MEDIUM):** Based on discord.py common issues + machine learning best practices; some scenarios not yet tested in chewyBot (e.g., DST transitions)
- **Parlay odds math (HIGH):** Formula verified via multiple betting sites; existing utils/odds_math.py handles conversions

**Research date:** 2026-03-31
**Valid until:** 2026-04-30 (balldontlie/discord.py are stable; low velocity API changes expected)
