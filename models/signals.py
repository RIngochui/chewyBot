from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class ArbSignal(BaseModel):
    """Detected arbitrage opportunity between two sportsbooks.

    arb_pct: percentage return if both sides staked proportionally
    stake_side_a/b: recommended stake amounts given a bankroll
    """
    market_key: str
    event_name: str
    sport: str
    market_type: str
    arb_pct: float
    stake_side_a: float
    stake_side_b: float
    estimated_profit: float
    book_a: str
    book_b: str
    odds_a: float
    odds_b: float
    selection_a: str
    selection_b: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class EVSignal(BaseModel):
    """Detected +EV (positive expected value) opportunity.

    ev_pct: expected value percentage above fair probability
    fair_probability: no-vig consensus probability of the outcome
    """
    market_key: str
    event_name: str
    sport: str
    market_type: str
    selection_name: str
    book_name: str
    decimal_odds: float
    fair_probability: float
    ev_pct: float
    detected_at: datetime = Field(default_factory=datetime.utcnow)
