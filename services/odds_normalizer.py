"""Odds normalizer: converts raw Odds API event dicts to NormalizedOdds records.

Implements ARB-06 canonical schema and ARB-07 key generation.
"""
from __future__ import annotations

from datetime import datetime

from models.odds import OddsSnapshot, NormalizedOdds  # OddsSnapshot kept for backwards compat
from utils.odds_math import decimal_to_american


def _slug(text: str) -> str:
    """Lowercase and replace spaces/hyphens with underscores."""
    return text.lower().replace(" ", "_").replace("-", "_")


async def normalize(
    event: dict,
    sport_key: str,
    league: str,
    supported_books: list[str] | None = None,
) -> list[NormalizedOdds]:
    """Normalize a raw Odds API event dict into a list of NormalizedOdds records.

    One record is produced per (bookmaker, market, outcome) combination.

    Args:
        event: Raw event dict from OddsApiAdapter (matches Odds API response shape).
        sport_key: Sport key string passed through to each record's ``sport`` field
                   (e.g. "basketball_nba").
        league: Human-readable league label (e.g. "NBA").
        supported_books: Optional whitelist of bookmaker keys to include.
                         If None, all bookmakers are included.
                         If an empty list, no bookmakers are included.

    Returns:
        List of NormalizedOdds, one per (bookmaker, market, outcome).
        Returns [] when the event has no bookmakers.

    ARB-07 key formats:
        event_id  = "{slug(home_team)}_{slug(away_team)}_{YYYYMMDD}"
        market_key = "{event_id}_{slug(market_key)}_{slug(outcome_name)}"
    """
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return []

    # Build event-level fields
    home_team = event["home_team"]
    away_team = event["away_team"]
    date_str = event["commence_time"][:10].replace("-", "")  # "20260401"
    event_id = f"{_slug(home_team)}_{_slug(away_team)}_{date_str}"
    event_name = f"{away_team} @ {home_team}"
    start_time = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))

    records: list[NormalizedOdds] = []

    for bookmaker in bookmakers:
        book_key = bookmaker["key"]
        if supported_books is not None and book_key not in supported_books:
            continue

        for market in bookmaker.get("markets", []):
            market_type = market["key"]
            for outcome in market.get("outcomes", []):
                price = outcome["price"]
                if not price or price <= 1.0:
                    continue  # invalid odds — skip to avoid division by zero
                market_key = f"{event_id}_{_slug(market_type)}_{_slug(outcome['name'])}"

                records.append(
                    NormalizedOdds(
                        event_id=event_id,
                        market_key=market_key,
                        sport=sport_key,
                        league=league,
                        event_name=event_name,
                        home_team=home_team,
                        away_team=away_team,
                        start_time=start_time,
                        market_type=market_type,
                        selection_name=outcome["name"],
                        line_value=outcome.get("point", None),
                        decimal_odds=price,
                        american_odds=decimal_to_american(price),
                        book_name=book_key,
                    )
                )

    return records
