from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Market(BaseModel):
    """A single betting market outcome from one sportsbook."""
    market_type: str
    selection_name: str
    line_value: Optional[float] = None
    decimal_odds: float
    american_odds: int
    book_name: str


class OddsSnapshot(BaseModel):
    """Raw odds data from a sportsbook API response before normalization."""
    event_id: str
    sport: str
    home_team: str
    away_team: str
    commence_time: datetime
    markets: list[Market]
    book_name: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class NormalizedOdds(BaseModel):
    """Canonical odds representation used throughout the scanning pipeline.

    event_id format: "{home_team}_{away_team}_{date}"  (ARB-07)
    market_key format: "{event_id}_{market_type}_{selection_name}"  (ARB-07)
    """
    event_id: str
    market_key: str
    sport: str
    league: str
    event_name: str
    home_team: str
    away_team: str
    start_time: datetime
    market_type: str
    selection_name: str
    line_value: Optional[float] = None
    decimal_odds: float
    american_odds: int
    book_name: str
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
