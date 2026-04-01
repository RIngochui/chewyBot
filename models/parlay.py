from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ParlayLeg(BaseModel):
    """A single leg within a parlay bet.

    leg_score: composite 0.0-1.0 score from 5-factor weighting (PAR-03)
    leg_type: category used for weight tracking; one of:
        h2h_favorite, h2h_underdog, spread_home, spread_away, totals_over, totals_under
    game_id: balldontlie/odds-api event id used for same-game dedup (PAR-04)
    """
    team: str
    market_type: str
    line_value: Optional[float] = None
    american_odds: int
    leg_score: float
    leg_type: str
    game_id: str = ""
    outcome: str = "pending"  # "pending" | "hit" | "miss"


class Parlay(BaseModel):
    """A generated NBA parlay with 3-5 legs.

    confidence_score: 0-100 composite confidence from leg scores
    discord_message_id: set after posting to Discord for reaction tracking
    """
    legs: list[ParlayLeg]
    combined_odds: float
    confidence_score: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: str = "pending"  # "pending" | "hit" | "miss"
    discord_message_id: Optional[str] = None
