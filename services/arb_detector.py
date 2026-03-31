from __future__ import annotations
from models.odds import NormalizedOdds
from models.signals import ArbSignal, EVSignal


async def detect_arb(
    normalized: list[NormalizedOdds],
    min_arb_pct: float,
    bankroll: float,
) -> list[ArbSignal]:
    """Detect arbitrage opportunities across sportsbooks.

    ARB-08: sum(1/best_odds) < 1.0 indicates arb exists.
    ARB-09: filters by min_arb_pct threshold, deduplicates by market_key.
    Phase 3 full implementation.
    """
    raise NotImplementedError("arb_detector.detect_arb() — implement in Phase 3")


async def detect_ev(
    normalized: list[NormalizedOdds],
    min_ev_pct: float,
) -> list[EVSignal]:
    """Detect +EV opportunities using no-vig consensus probability.

    ARB-10: ev_pct = ((offered_decimal * fair_prob) - 1) * 100
    Phase 3 full implementation.
    """
    raise NotImplementedError("arb_detector.detect_ev() — implement in Phase 3")
