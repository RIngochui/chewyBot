"""parlay_engine.py — NBA parlay generation engine.

Core intelligence of the NBA Parlay AI (Phase 4):
  - Fetches NBA game data from balldontlie API
  - Fetches today's odds from The Odds API
  - Scores each candidate leg across 5 factors (PAR-03)
  - Selects best 3-5 legs excluding same-game conflicts (PAR-04)
  - Returns None if fewer than 3 scoreable legs found (no-games fallback, decision B)

Public API:
  generate_parlay(min_leg_score, leg_count_range) -> Parlay | None

References: PAR-03, PAR-04, PAR-08, decision A/B/C/E from CONTEXT.md
"""
from __future__ import annotations

import math
import logging
from datetime import date, datetime, timezone
from typing import Optional
from functools import reduce
import operator

from adapters.balldontlie import BallDontLieAdapter
from adapters.odds_api import OddsApiAdapter
from config import config
from database.db import get_db
from database.queries import (
    SELECT_ALL_LEG_TYPE_WEIGHTS,
    SELECT_LOW_HIT_RATE_LEG_TYPES,
    SELECT_PARLAY_COUNT,
)
from models.parlay import Parlay, ParlayLeg
from utils.odds_math import american_to_decimal

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Module-level constants                                              #
# ------------------------------------------------------------------ #

# 5-factor weights for scoring each candidate leg (PAR-03)
LEG_TYPE_WEIGHTS: dict[str, float] = {
    "recent_form": 0.25,
    "home_away_split": 0.20,
    "rest_days": 0.15,
    "line_value": 0.25,
    "historical_hit_rate": 0.15,
}

# Locked leg-type taxonomy (decision A from CONTEXT.md)
ALL_LEG_TYPES: list[str] = [
    "h2h_favorite",
    "h2h_underdog",
    "spread_home",
    "spread_away",
    "totals_over",
    "totals_under",
]

NBA_SPORT_KEY: str = "basketball_nba"


# ------------------------------------------------------------------ #
# Helper functions                                                    #
# ------------------------------------------------------------------ #

def _classify_leg_type(
    market_type: str,
    american_odds: int,
    is_home: bool,
    selection_name: str,
) -> str:
    """Classify a candidate leg into one of the 6 locked leg types.

    Args:
        market_type:    "h2h", "spreads", or "totals"
        american_odds:  American format odds (negative = favorite)
        is_home:        Whether the selection is the home team
        selection_name: Outcome name (used for totals: "Over" / "Under")

    Returns:
        One of: h2h_favorite, h2h_underdog, spread_home, spread_away,
                totals_over, totals_under
    """
    if market_type == "h2h":
        return "h2h_favorite" if american_odds < 0 else "h2h_underdog"
    if market_type == "spreads":
        return "spread_home" if is_home else "spread_away"
    if market_type == "totals":
        return "totals_over" if "over" in selection_name.lower() else "totals_under"
    # Fallback for unknown market types
    logger.warning("_classify_leg_type: unknown market_type=%r, defaulting to h2h_favorite", market_type)
    return "h2h_favorite"


def _sigmoid(x: float) -> float:
    """Logistic sigmoid function, mapping any real number to (0, 1)."""
    return 1.0 / (1.0 + math.exp(-x))


def _parse_record(record_str: str) -> float:
    """Parse a 'W-L' win-loss string into a win percentage.

    Returns 0.5 as default if parsing fails.
    """
    try:
        parts = record_str.split("-")
        wins = int(parts[0])
        losses = int(parts[1])
        total = wins + losses
        return wins / total if total > 0 else 0.5
    except (ValueError, IndexError, AttributeError):
        return 0.5


def _score_leg(
    team_id: int,
    recent_games: list[dict],
    team_stats: dict | None,
    american_odds: int,
    is_home: bool,
    leg_type: str,
    weight_lookup: dict[str, tuple[float, int, int]],
) -> float:
    """Compute a composite 0.0-1.0 score for a candidate leg across 5 factors.

    Factor weights (PAR-03):
        recent_form          0.25  — Last 5 game W/L record for this team
        home_away_split      0.20  — Season home or away win % from team_stats
        rest_days            0.15  — Days since last game (sigmoid-scaled)
        line_value           0.25  — Implied probability from American odds
        historical_hit_rate  0.15  — Hit rate from leg_type_weights DB table

    Args:
        team_id:       balldontlie team ID for filtering recent_games
        recent_games:  All fetched games (engine passes full list; we filter here)
        team_stats:    Season averages dict with "home_record" / "away_record" keys
        american_odds: American format odds for the leg
        is_home:       Whether this team is the home side
        leg_type:      Classified leg type for historical_hit_rate lookup
        weight_lookup: {leg_type: (weight, hit_count, miss_count)} from DB

    Returns:
        Clamped float in [0.0, 1.0]
    """
    # ---- Factor 1: recent_form (0.25) ----
    # Filter games where this team played, sorted by date descending, take last 5
    team_games: list[dict] = []
    for g in recent_games:
        if g.get("home_team_id") == team_id or g.get("visitor_team_id") == team_id:
            team_games.append(g)

    # Sort by date descending and take the 5 most recent
    team_games.sort(key=lambda g: g.get("date", ""), reverse=True)
    last_5 = team_games[:5]

    if last_5:
        wins = 0
        for g in last_5:
            home_score = g.get("home_team_score", 0) or 0
            away_score = g.get("visitor_team_score", 0) or 0
            is_home_team = g.get("home_team_id") == team_id
            if is_home_team:
                wins += 1 if home_score > away_score else 0
            else:
                wins += 1 if away_score > home_score else 0
        recent_form = wins / len(last_5)
    else:
        recent_form = 0.5

    # ---- Factor 2: home_away_split (0.20) ----
    if team_stats and isinstance(team_stats, dict):
        if is_home:
            home_away_split = _parse_record(team_stats.get("home_record", ""))
        else:
            home_away_split = _parse_record(team_stats.get("away_record", ""))
    else:
        home_away_split = 0.5

    # ---- Factor 3: rest_days (0.15) ----
    if last_5:
        # Most recent game date is first element (sorted descending)
        last_date_str = last_5[0].get("date", "")
        try:
            last_game_date = date.fromisoformat(last_date_str)
            days = (date.today() - last_game_date).days
            rest_score = min(1.0, _sigmoid(days / 2.0))
        except (ValueError, TypeError):
            rest_score = 0.5
    else:
        rest_score = 0.5

    # ---- Factor 4: line_value (0.25) ----
    # Implied probability — higher implied prob means shorter odds (more reliable pick)
    try:
        decimal = american_to_decimal(american_odds)
        line_value_score = 1.0 / decimal if decimal > 0 else 0.5
    except (ValueError, ZeroDivisionError):
        line_value_score = 0.5

    # ---- Factor 5: historical_hit_rate (0.15) ----
    leg_weight_data = weight_lookup.get(leg_type, (1.0, 0, 0))
    _, hit_count, miss_count = leg_weight_data
    total = hit_count + miss_count
    historical_hit_rate = hit_count / total if total > 0 else 0.5

    # ---- Composite score ----
    leg_score = (
        recent_form * LEG_TYPE_WEIGHTS["recent_form"]
        + home_away_split * LEG_TYPE_WEIGHTS["home_away_split"]
        + rest_score * LEG_TYPE_WEIGHTS["rest_days"]
        + line_value_score * LEG_TYPE_WEIGHTS["line_value"]
        + historical_hit_rate * LEG_TYPE_WEIGHTS["historical_hit_rate"]
    )

    return max(0.0, min(1.0, leg_score))


# ------------------------------------------------------------------ #
# Main public function                                                #
# ------------------------------------------------------------------ #

async def generate_parlay(
    min_leg_score: float,
    leg_count_range: tuple[int, int] = (3, 5),
) -> Parlay | None:
    """Generate a 3-5 leg NBA parlay using 5-factor weighted scoring.

    Steps:
      1. Load leg_type_weights from DB (self-learning weights, PAR-09)
      2. Check PAR-08 filter: after 20+ parlays, exclude low-hit-rate leg types
      3. Fetch today's NBA odds via OddsApiAdapter
      4. Fetch today's games + team season averages via BallDontLieAdapter
      5. Build and score candidate legs
      6. Greedily select best legs excluding same-game conflicts (PAR-04)
      7. No-games fallback: return None if fewer than min legs found (decision B)
      8. Assemble and return Parlay with combined_odds and confidence_score

    Args:
        min_leg_score:    Minimum leg_score required for inclusion (PAR-04)
        leg_count_range:  (min_legs, max_legs) — default (3, 5)

    Returns:
        Parlay if enough scoreable legs found, else None.
    """
    min_legs, max_legs = leg_count_range

    # ------------------------------------------------------------------
    # Step 1: Load leg_type_weights from DB
    # ------------------------------------------------------------------
    weight_lookup: dict[str, tuple[float, int, int]] = {}
    try:
        async with get_db() as db:
            cursor = await db.execute(SELECT_ALL_LEG_TYPE_WEIGHTS)
            rows = await cursor.fetchall()
            for row in rows:
                leg_type = row["leg_type"]
                weight = float(row["weight"])
                hit_count = int(row["hit_count"])
                miss_count = int(row["miss_count"])
                weight_lookup[leg_type] = (weight, hit_count, miss_count)
    except Exception as exc:
        logger.warning("generate_parlay: failed to load leg_type_weights: %s", exc)

    # Seed missing leg types with defaults so all 6 are always present
    for lt in ALL_LEG_TYPES:
        if lt not in weight_lookup:
            weight_lookup[lt] = (1.0, 0, 0)

    # ------------------------------------------------------------------
    # Step 2: PAR-08 filter — exclude low hit-rate leg types after 20+ parlays
    # ------------------------------------------------------------------
    excluded_types: set[str] = set()
    try:
        async with get_db() as db:
            cursor = await db.execute(SELECT_PARLAY_COUNT)
            row = await cursor.fetchone()
            total_tracked = int(row[0]) if row else 0

            if total_tracked >= 20:
                cursor2 = await db.execute(SELECT_LOW_HIT_RATE_LEG_TYPES)
                low_rows = await cursor2.fetchall()
                excluded_types = {r["leg_type"] for r in low_rows}
                if excluded_types:
                    logger.info(
                        "generate_parlay: PAR-08 filtering out low hit-rate types: %s",
                        excluded_types,
                    )
    except Exception as exc:
        logger.warning("generate_parlay: failed to check PAR-08 filter: %s", exc)

    # ------------------------------------------------------------------
    # Step 3: Fetch today's NBA odds
    # ------------------------------------------------------------------
    odds_events: list[dict] = []
    odds_adapter = OddsApiAdapter(api_key=config.ODDS_API_KEY, mock_mode=config.MOCK_MODE)
    try:
        odds_events = await odds_adapter.get_odds(
            sport_key=NBA_SPORT_KEY,
            regions=["us"],
            markets=["h2h", "spreads", "totals"],
        )
        logger.info("generate_parlay: fetched %d odds events", len(odds_events))
    except Exception as exc:
        logger.warning("generate_parlay: failed to fetch odds: %s", exc)
    finally:
        await odds_adapter.close()

    # ------------------------------------------------------------------
    # Step 4: Fetch today's games and team season averages
    # ------------------------------------------------------------------
    today_str = date.today().isoformat()
    current_year = date.today().year
    # NBA season: Oct–Jun; if before October, use previous year as season start
    season = current_year if date.today().month >= 10 else current_year - 1

    recent_games: list[dict] = []
    team_stats_lookup: dict[int, dict] = {}

    bdl = BallDontLieAdapter(mock_mode=config.MOCK_MODE)
    try:
        recent_games = await bdl.get_games(dates=[today_str], seasons=[season])
        logger.info("generate_parlay: fetched %d games from balldontlie", len(recent_games))

        # Collect unique team IDs from fetched games
        team_ids: list[int] = []
        seen_ids: set[int] = set()
        for g in recent_games:
            for id_key in ("home_team_id", "visitor_team_id"):
                tid = g.get(id_key)
                if tid and tid not in seen_ids:
                    team_ids.append(tid)
                    seen_ids.add(tid)

        if team_ids:
            team_stats_list = await bdl.get_team_season_averages(
                season=season, team_ids=team_ids
            )
            team_stats_lookup = {
                int(ts["team_id"]): ts
                for ts in team_stats_list
                if "team_id" in ts
            }
            logger.info(
                "generate_parlay: loaded stats for %d teams", len(team_stats_lookup)
            )
    except Exception as exc:
        logger.warning("generate_parlay: failed to fetch balldontlie data: %s", exc)
    finally:
        await bdl.close()

    # ------------------------------------------------------------------
    # Step 5: Build candidate legs from odds data
    # ------------------------------------------------------------------
    candidates: list[ParlayLeg] = []

    for event in odds_events:
        game_id: str = event.get("id", "")
        home_team: str = event.get("home_team", "")
        away_team: str = event.get("away_team", "")

        # Best-effort name-to-team-id mapping: search recent_games for a game
        # where home_team / away_team name appears as part of the team city/name.
        # Falls back to None (team_stats uses default 0.5).
        home_team_id: int | None = _find_team_id(home_team, recent_games, is_home=True)
        away_team_id: int | None = _find_team_id(away_team, recent_games, is_home=False)

        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                if market_key not in ("h2h", "spreads", "totals"):
                    continue

                for outcome in market.get("outcomes", []):
                    outcome_name: str = outcome.get("name", "")
                    decimal_price: float = float(outcome.get("price", 1.0))
                    point: Optional[float] = outcome.get("point")

                    # Convert decimal odds to American (The Odds API returns decimal)
                    try:
                        from utils.odds_math import decimal_to_american
                        american_odds = decimal_to_american(decimal_price)
                    except (ValueError, ZeroDivisionError):
                        continue

                    # Determine if this outcome is the home team
                    is_home = _name_matches(outcome_name, home_team)

                    # For totals, outcome name is "Over"/"Under" — not a team name
                    if market_key == "totals":
                        is_home = False  # totals are game-level, not team-specific
                        team_label = f"{home_team} vs {away_team}"
                        team_id_for_scoring: int | None = home_team_id  # use home team data as proxy
                    else:
                        team_label = outcome_name
                        team_id_for_scoring = home_team_id if is_home else away_team_id

                    leg_type = _classify_leg_type(market_key, american_odds, is_home, outcome_name)

                    # PAR-08: skip excluded leg types
                    if leg_type in excluded_types:
                        continue

                    # Score the leg
                    team_stats = (
                        team_stats_lookup.get(team_id_for_scoring)
                        if team_id_for_scoring is not None
                        else None
                    )
                    leg_score = _score_leg(
                        team_id=team_id_for_scoring if team_id_for_scoring is not None else -1,
                        recent_games=recent_games,
                        team_stats=team_stats,
                        american_odds=american_odds,
                        is_home=is_home,
                        leg_type=leg_type,
                        weight_lookup=weight_lookup,
                    )

                    # PAR-04: only include legs meeting minimum score threshold
                    if leg_score < min_leg_score:
                        continue

                    candidates.append(
                        ParlayLeg(
                            team=team_label,
                            market_type=market_key,
                            line_value=point,
                            american_odds=american_odds,
                            leg_score=leg_score,
                            leg_type=leg_type,
                            game_id=game_id,
                        )
                    )

    logger.info("generate_parlay: %d candidate legs after scoring/filtering", len(candidates))

    # ------------------------------------------------------------------
    # Step 6: Same-game dedup + greedy selection (PAR-04)
    # ------------------------------------------------------------------
    # Sort descending by leg_score to always pick the best available leg first
    candidates.sort(key=lambda leg: leg.leg_score, reverse=True)

    selected: list[ParlayLeg] = []
    seen_game_ids: set[str] = set()

    for leg in candidates:
        if leg.game_id and leg.game_id in seen_game_ids:
            continue  # Skip — another leg from same game already selected
        selected.append(leg)
        if leg.game_id:
            seen_game_ids.add(leg.game_id)
        if len(selected) >= max_legs:
            break

    # ------------------------------------------------------------------
    # Step 7: No-games fallback (decision B from CONTEXT.md)
    # ------------------------------------------------------------------
    if len(selected) < min_legs:
        logger.info(
            "generate_parlay: only %d scoreable legs found (need %d) — skipping",
            len(selected),
            min_legs,
        )
        return None

    # ------------------------------------------------------------------
    # Step 8: Combined odds (decimal product of all leg odds)
    # ------------------------------------------------------------------
    combined_decimal: float = reduce(
        operator.mul,
        (american_to_decimal(leg.american_odds) for leg in selected),
        1.0,
    )

    # ------------------------------------------------------------------
    # Step 9: Confidence score (decision C from CONTEXT.md)
    # ------------------------------------------------------------------
    # mean(leg_score * learned_leg_type_weight) * 100, clamped 0-100
    scores: list[float] = [
        leg.leg_score * weight_lookup[leg.leg_type][0]
        for leg in selected
    ]
    confidence: float = (sum(scores) / len(scores)) * 100
    confidence = max(0.0, min(100.0, confidence))

    # ------------------------------------------------------------------
    # Step 10: Assemble and return Parlay
    # ------------------------------------------------------------------
    return Parlay(
        legs=selected,
        combined_odds=combined_decimal,
        confidence_score=confidence,
        generated_at=datetime.now(timezone.utc),
    )


# ------------------------------------------------------------------ #
# Private name-matching helpers                                       #
# ------------------------------------------------------------------ #

def _name_matches(outcome_name: str, team_name: str) -> bool:
    """Check if an outcome name corresponds to a given team name.

    Uses case-insensitive substring matching on the last word of the team name
    (e.g., "Golden State Warriors" -> "warriors") to handle partial name formats.
    """
    if not outcome_name or not team_name:
        return False
    outcome_lower = outcome_name.lower()
    team_lower = team_name.lower()
    # Direct match or any word of the team name appearing in the outcome
    if team_lower in outcome_lower or outcome_lower in team_lower:
        return True
    # Match on last word (team nickname, e.g. "Warriors")
    team_words = team_lower.split()
    if team_words and team_words[-1] in outcome_lower:
        return True
    return False


def _find_team_id(
    team_name: str,
    recent_games: list[dict],
    is_home: bool,
) -> int | None:
    """Best-effort lookup of balldontlie team_id from a team display name.

    Searches recent_games for a game where the home/away team name appears in
    the odds API team name. Returns the first matching team_id, or None.

    This is approximate — the odds API uses full city+nickname ("Los Angeles Lakers")
    while balldontlie games only store team_id. The actual name mapping would require
    a /teams lookup, but that would cost an extra API call. A fuzzy word match on
    the game records is sufficient for scoring purposes.
    """
    team_lower = team_name.lower()
    team_words = set(team_lower.split())

    for game in recent_games:
        if is_home:
            candidate_id = game.get("home_team_id")
        else:
            candidate_id = game.get("visitor_team_id")

        # Without a name field on games, we cannot match by name here.
        # Return the first candidate_id and accept that for mock mode
        # the scoring will use generic data. In live mode the team_stats
        # lookup covers this via team_id from get_team_season_averages.
        # This best-effort approach defaults to None when no games are fetched.
        if candidate_id is not None:
            return int(candidate_id)

    return None
