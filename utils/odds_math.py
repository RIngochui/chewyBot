from __future__ import annotations


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds.

    Examples: +150 -> 2.5, -110 -> 1.909
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("american_to_decimal() — implement in Phase 3")


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds.

    Examples: 2.5 -> +150, 1.909 -> -110
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("decimal_to_american() — implement in Phase 3")


def implied_probability(decimal_odds: float) -> float:
    """Return implied probability from decimal odds.

    Formula: 1 / decimal_odds
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("implied_probability() — implement in Phase 3")


def no_vig_probability(odds_list: list[float]) -> list[float]:
    """Remove vig from a list of decimal odds and return fair probabilities.

    Used by +EV detector (ARB-10) to establish consensus fair line.
    Phase 3 full implementation (ARB-11).
    """
    raise NotImplementedError("no_vig_probability() — implement in Phase 3")
