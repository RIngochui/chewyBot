from __future__ import annotations


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds.

    Examples: +150 -> 2.5, -110 -> ~1.909
    Formula (ARB-11):
      positive: (american_odds / 100) + 1.0
      negative: (100 / abs(american_odds)) + 1.0
    """
    if american_odds == 0:
        raise ValueError("american_odds cannot be zero")
    if american_odds > 0:
        return (american_odds / 100) + 1.0
    else:
        return (100 / abs(american_odds)) + 1.0


def decimal_to_american(decimal_odds: float) -> int:
    """Convert decimal odds to American odds.

    Examples: 2.5 -> +150, 1.909 -> -110
    Formula (ARB-11):
      decimal >= 2.0: round((decimal_odds - 1) * 100)
      decimal <  2.0: round(-100 / (decimal_odds - 1))
    """
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal_odds must be > 1.0, got {decimal_odds}")
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1) * 100)
    else:
        return round(-100 / (decimal_odds - 1))


def implied_probability(decimal_odds: float) -> float:
    """Return implied probability from decimal odds.

    Formula: 1 / decimal_odds
    """
    return 1.0 / decimal_odds


def no_vig_probability(odds_list: list[float]) -> list[float]:
    """Remove vig from a list of decimal odds and return fair probabilities.

    Used by +EV detector (ARB-10) to establish consensus fair line.
    Formula: normalise raw implied probabilities so they sum to 1.0.
    """
    raw_probs = [1.0 / o for o in odds_list]
    total = sum(raw_probs)
    return [p / total for p in raw_probs]
