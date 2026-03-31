from __future__ import annotations
from models.parlay import Parlay


async def generate_parlay(
    min_leg_score: float,
    leg_count_range: tuple[int, int] = (3, 5),
) -> Parlay:
    """Generate a 3-5 leg NBA parlay using 5-factor weighted scoring.

    PAR-03 factors: recent_form (0.25), home_away_split (0.20),
                    rest_days (0.15), line_value (0.25), historical_hit_rate (0.15)
    PAR-04: Never includes both sides of same game; min leg_score >= min_leg_score.
    Phase 4 full implementation.
    """
    raise NotImplementedError("parlay_engine.generate_parlay() — implement in Phase 4")
