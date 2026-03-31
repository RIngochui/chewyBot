from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from models.odds import NormalizedOdds
from models.signals import ArbSignal, EVSignal
from utils.odds_math import no_vig_probability


async def detect_arb(
    normalized: list[NormalizedOdds],
    min_arb_pct: float,
    bankroll: float,
) -> list[ArbSignal]:
    """Detect arbitrage opportunities across sportsbooks.

    ARB-08: sum(1/best_odds) < 1.0 indicates arb exists.
    ARB-09: filters by min_arb_pct threshold, deduplicates by market_key.
    Phase 3 full implementation.

    Algorithm:
    1. Group records by (event_id, market_type)
    2. Find best (highest) decimal_odds per selection across all books
    3. If sum(1/best_odds_per_selection) < 1.0 → arb exists
    4. Compute arb_pct, stakes, and profit; append ArbSignal if above threshold
    """
    signals: list[ArbSignal] = []

    # Group by (event_id, market_type)
    groups: dict[tuple[str, str], list[NormalizedOdds]] = defaultdict(list)
    for rec in normalized:
        groups[(rec.event_id, rec.market_type)].append(rec)

    for (event_id, market_type), records in groups.items():
        # Best odds per selection: (odds, book_name, market_key)
        best: dict[str, tuple[float, str, str]] = {}
        for rec in records:
            if rec.selection_name not in best or rec.decimal_odds > best[rec.selection_name][0]:
                best[rec.selection_name] = (rec.decimal_odds, rec.book_name, rec.market_key)

        # Need at least 2 selections to form an arb
        if len(best) < 2:
            continue

        sum_implied = sum(1.0 / odds for odds, _, _ in best.values())
        if sum_implied >= 1.0:
            continue

        arb_pct = (1.0 - sum_implied) * 100
        if arb_pct < min_arb_pct:
            continue

        # Build signal from first two selections
        selections = list(best.items())
        sel_a, (odds_a, book_a, mkey) = selections[0]
        sel_b, (odds_b, book_b, _) = selections[1]

        stake_a = round(bankroll * (1.0 / odds_a) / sum_implied, 2)
        stake_b = round(bankroll * (1.0 / odds_b) / sum_implied, 2)
        profit = round(bankroll * arb_pct / 100, 2)

        signals.append(ArbSignal(
            market_key=mkey,
            event_name=records[0].event_name,
            sport=records[0].sport,
            market_type=market_type,
            arb_pct=round(arb_pct, 4),
            stake_side_a=stake_a,
            stake_side_b=stake_b,
            estimated_profit=profit,
            book_a=book_a,
            book_b=book_b,
            odds_a=odds_a,
            odds_b=odds_b,
            selection_a=sel_a,
            selection_b=sel_b,
            detected_at=datetime.utcnow(),
        ))

    return signals


async def detect_ev(
    normalized: list[NormalizedOdds],
    min_ev_pct: float,
) -> list[EVSignal]:
    """Detect +EV opportunities using no-vig consensus probability.

    ARB-10: ev_pct = ((offered_decimal * fair_prob) - 1) * 100
    Phase 3 full implementation.

    Algorithm:
    1. Group records by (event_id, market_type)
    2. Gather all offered decimal odds for the group
    3. Compute fair (no-vig) probabilities via no_vig_probability()
    4. For each record, compute ev_pct; yield EVSignal if above threshold
    """
    signals: list[EVSignal] = []

    # Group by (event_id, market_type)
    groups: dict[tuple[str, str], list[NormalizedOdds]] = defaultdict(list)
    for rec in normalized:
        groups[(rec.event_id, rec.market_type)].append(rec)

    for (event_id, market_type), records in groups.items():
        if not records:
            continue

        # Compute fair probability per selection using no_vig consensus.
        # Strategy: collect all unique selection names in their natural order,
        # then for each unique selection compute the average offered odds across
        # all books. Apply no_vig_probability() over the per-selection averages
        # to get the consensus fair probability for each selection.
        #
        # This matches the plan intent: "compute fair probabilities via
        # no_vig_probability() across all offered decimal odds for that market"
        # — the "all odds" are grouped per selection first so each selection gets
        # one fair probability that accounts for the vig.

        # Collect ordered unique selections and per-selection offered odds
        sel_order: list[str] = []
        sel_odds: dict[str, list[float]] = defaultdict(list)
        for rec in records:
            if rec.selection_name not in sel_odds:
                sel_order.append(rec.selection_name)
            sel_odds[rec.selection_name].append(rec.decimal_odds)

        if not sel_order:
            continue

        # Average odds per selection → representative line for no_vig
        avg_odds_per_sel = [
            sum(sel_odds[sel]) / len(sel_odds[sel]) for sel in sel_order
        ]
        fair_probs_list = no_vig_probability(avg_odds_per_sel)
        # Map selection_name → fair_probability
        fair_prob_map: dict[str, float] = {
            sel: fp for sel, fp in zip(sel_order, fair_probs_list)
        }

        # For each record, compare offered odds against fair probability
        for rec in records:
            fair_prob = fair_prob_map.get(rec.selection_name)
            if fair_prob is None:
                continue
            ev_pct = ((rec.decimal_odds * fair_prob) - 1) * 100
            if ev_pct >= min_ev_pct:
                signals.append(EVSignal(
                    market_key=rec.market_key,
                    event_name=rec.event_name,
                    sport=rec.sport,
                    market_type=market_type,
                    selection_name=rec.selection_name,
                    book_name=rec.book_name,
                    decimal_odds=rec.decimal_odds,
                    fair_probability=round(fair_prob, 6),
                    ev_pct=round(ev_pct, 4),
                    detected_at=datetime.utcnow(),
                ))

    return signals
