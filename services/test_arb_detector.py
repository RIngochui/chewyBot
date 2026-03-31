"""Tests for services/arb_detector.py — detect_arb() and detect_ev()."""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime

from models.odds import NormalizedOdds
from models.signals import ArbSignal, EVSignal


# ---------------------------------------------------------------------------
# Helpers — build NormalizedOdds records
# ---------------------------------------------------------------------------

def _make_record(
    event_id: str = "los_angeles_lakers_golden_state_warriors_20260401",
    market_key: str = "los_angeles_lakers_golden_state_warriors_20260401_h2h_los_angeles_lakers",
    sport: str = "basketball_nba",
    league: str = "NBA",
    event_name: str = "Los Angeles Lakers vs Golden State Warriors",
    home_team: str = "Golden State Warriors",
    away_team: str = "Los Angeles Lakers",
    start_time: datetime = datetime(2026, 4, 1, 2, 0, 0),
    market_type: str = "h2h",
    selection_name: str = "Los Angeles Lakers",
    line_value: float | None = None,
    decimal_odds: float = 2.0,
    american_odds: int = 100,
    book_name: str = "fanduel",
) -> NormalizedOdds:
    return NormalizedOdds(
        event_id=event_id,
        market_key=market_key,
        sport=sport,
        league=league,
        event_name=event_name,
        home_team=home_team,
        away_team=away_team,
        start_time=start_time,
        market_type=market_type,
        selection_name=selection_name,
        line_value=line_value,
        decimal_odds=decimal_odds,
        american_odds=american_odds,
        book_name=book_name,
    )


def _lakers_warriors_arb_records() -> list[NormalizedOdds]:
    """Lakers/Warriors mock records with known 10.1% arb.

    FanDuel: Lakers 2.20, Warriors 1.75
    DraftKings: Lakers 1.65, Warriors 2.25

    Best per selection: Lakers=2.20 (FanDuel), Warriors=2.25 (DraftKings)
    sum_implied = 1/2.20 + 1/2.25 = 0.4545... + 0.4444... = 0.899...
    arb_pct = (1 - 0.899) * 100 ≈ 10.1%
    """
    event_id = "los_angeles_lakers_golden_state_warriors_20260401"
    start_time = datetime(2026, 4, 1, 2, 0, 0)

    return [
        # FanDuel h2h
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_los_angeles_lakers",
            market_type="h2h",
            selection_name="Los Angeles Lakers",
            decimal_odds=2.20,
            american_odds=120,
            book_name="fanduel",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_golden_state_warriors",
            market_type="h2h",
            selection_name="Golden State Warriors",
            decimal_odds=1.75,
            american_odds=-133,
            book_name="fanduel",
            start_time=start_time,
        ),
        # DraftKings h2h
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_los_angeles_lakers",
            market_type="h2h",
            selection_name="Los Angeles Lakers",
            decimal_odds=1.65,
            american_odds=-154,
            book_name="draftkings",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_golden_state_warriors",
            market_type="h2h",
            selection_name="Golden State Warriors",
            decimal_odds=2.25,
            american_odds=125,
            book_name="draftkings",
            start_time=start_time,
        ),
    ]


def _no_arb_records() -> list[NormalizedOdds]:
    """Records where no arb exists (sum_implied > 1.0)."""
    event_id = "team_a_team_b_20260401"
    start_time = datetime(2026, 4, 1, 2, 0, 0)
    return [
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_a",
            market_type="h2h",
            selection_name="Team A",
            decimal_odds=1.80,
            american_odds=-125,
            book_name="fanduel",
            event_name="Team A vs Team B",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_b",
            market_type="h2h",
            selection_name="Team B",
            decimal_odds=1.80,
            american_odds=-125,
            book_name="draftkings",
            event_name="Team A vs Team B",
            start_time=start_time,
        ),
    ]


def _ev_records() -> list[NormalizedOdds]:
    """Records for EV detection test.

    FanDuel: Lakers 2.20, Warriors 1.75  (total implied = 1/2.20 + 1/2.75 ~ this set)
    Use simple case: two books with divergent lines so one side has +EV.

    Book A: Team A 2.10, Team B 1.90  → sum_imp = 0.476 + 0.526 = 1.002
    No-vig: [0.476/1.002, 0.526/1.002] = [0.475, 0.525]

    Book B: Team A 2.20 → ev_pct = (2.20 * 0.475 - 1) * 100 = 4.5%
    Book B: Team B 1.70 → ev_pct = (1.70 * 0.525 - 1) * 100 = -10.75% (negative)
    """
    event_id = "team_x_team_y_20260401"
    start_time = datetime(2026, 4, 1, 2, 0, 0)
    return [
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_x",
            market_type="h2h",
            selection_name="Team X",
            decimal_odds=2.10,
            american_odds=110,
            book_name="book_a",
            event_name="Team X vs Team Y",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_y",
            market_type="h2h",
            selection_name="Team Y",
            decimal_odds=1.90,
            american_odds=-111,
            book_name="book_a",
            event_name="Team X vs Team Y",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_x",
            market_type="h2h",
            selection_name="Team X",
            decimal_odds=2.20,
            american_odds=120,
            book_name="book_b",
            event_name="Team X vs Team Y",
            start_time=start_time,
        ),
        _make_record(
            event_id=event_id,
            market_key=f"{event_id}_h2h_team_y",
            market_type="h2h",
            selection_name="Team Y",
            decimal_odds=1.70,
            american_odds=-143,
            book_name="book_b",
            event_name="Team X vs Team Y",
            start_time=start_time,
        ),
    ]


# ---------------------------------------------------------------------------
# detect_arb tests
# ---------------------------------------------------------------------------

class TestDetectArbFindsKnownArb:
    def test_finds_lakers_warriors_arb(self):
        """detect_arb must find the ~10.1% Lakers/Warriors arb."""
        from services.arb_detector import detect_arb

        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        assert len(signals) == 1
        sig = signals[0]
        assert isinstance(sig, ArbSignal)
        assert abs(sig.arb_pct - 10.1) < 0.5, f"Expected ~10.1%, got {sig.arb_pct}"

    def test_arb_signal_correct_books(self):
        """ArbSignal must identify best books for each side."""
        from services.arb_detector import detect_arb

        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        assert len(signals) == 1
        sig = signals[0]
        # Lakers best odds at FanDuel (2.20), Warriors best at DraftKings (2.25)
        books = {sig.book_a, sig.book_b}
        assert "fanduel" in books
        assert "draftkings" in books

    def test_arb_signal_correct_odds(self):
        """ArbSignal must use best decimal odds for each side."""
        from services.arb_detector import detect_arb

        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        sig = signals[0]
        odds_in_signal = {sig.odds_a, sig.odds_b}
        assert 2.20 in odds_in_signal
        assert 2.25 in odds_in_signal

    def test_arb_signal_stakes_sum_to_bankroll(self):
        """stake_side_a + stake_side_b must approximately equal bankroll."""
        from services.arb_detector import detect_arb

        bankroll = 100.0
        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=bankroll))

        sig = signals[0]
        total = sig.stake_side_a + sig.stake_side_b
        assert abs(total - bankroll) < 0.02, f"Stakes {total} don't sum to bankroll {bankroll}"

    def test_arb_signal_estimated_profit(self):
        """estimated_profit must be bankroll * arb_pct / 100."""
        from services.arb_detector import detect_arb

        bankroll = 100.0
        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=bankroll))

        sig = signals[0]
        expected = round(bankroll * sig.arb_pct / 100, 2)
        assert abs(sig.estimated_profit - expected) < 0.01

    def test_arb_signal_has_event_info(self):
        """ArbSignal must contain event_name, sport, market_type."""
        from services.arb_detector import detect_arb

        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        sig = signals[0]
        assert sig.event_name != ""
        assert sig.sport == "basketball_nba"
        assert sig.market_type == "h2h"
        assert sig.market_key != ""

    def test_arb_signal_has_detected_at(self):
        """ArbSignal detected_at must be a datetime."""
        from services.arb_detector import detect_arb

        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        assert isinstance(signals[0].detected_at, datetime)


class TestDetectArbNoOpportunity:
    def test_returns_empty_when_no_arb(self):
        """detect_arb returns [] when sum_implied >= 1.0."""
        from services.arb_detector import detect_arb

        records = _no_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=0.5, bankroll=100.0))

        assert signals == []

    def test_returns_empty_for_empty_input(self):
        """detect_arb returns [] for empty input."""
        from services.arb_detector import detect_arb

        signals = asyncio.run(detect_arb([], min_arb_pct=0.5, bankroll=100.0))
        assert signals == []

    def test_respects_min_arb_pct_threshold(self):
        """detect_arb filters out arbs below min_arb_pct."""
        from services.arb_detector import detect_arb

        # The Lakers/Warriors arb is ~10.1%, filter to >15% should return []
        records = _lakers_warriors_arb_records()
        signals = asyncio.run(detect_arb(records, min_arb_pct=15.0, bankroll=100.0))
        assert signals == []

    def test_skips_single_selection_markets(self):
        """detect_arb skips markets with only 1 selection."""
        from services.arb_detector import detect_arb

        # Only one selection → can't form arb
        single = [_make_record(selection_name="Team A", decimal_odds=1.50)]
        signals = asyncio.run(detect_arb(single, min_arb_pct=0.5, bankroll=100.0))
        assert signals == []


# ---------------------------------------------------------------------------
# detect_ev tests
# ---------------------------------------------------------------------------

class TestDetectEvFindsPositiveEV:
    def test_finds_positive_ev_opportunity(self):
        """detect_ev returns EVSignal when offered odds beat fair probability."""
        from services.arb_detector import detect_ev

        records = _ev_records()
        signals = asyncio.run(detect_ev(records, min_ev_pct=2.0))

        # book_b's Team X at 2.20 should have ~4.5% EV
        assert len(signals) >= 1
        for s in signals:
            assert s.ev_pct >= 2.0

    def test_ev_signal_has_correct_structure(self):
        """EVSignal must have all required fields populated."""
        from services.arb_detector import detect_ev

        records = _ev_records()
        signals = asyncio.run(detect_ev(records, min_ev_pct=1.0))

        assert len(signals) >= 1
        sig = signals[0]
        assert isinstance(sig, EVSignal)
        assert sig.market_key != ""
        assert sig.event_name != ""
        assert sig.book_name != ""
        assert sig.decimal_odds > 1.0
        assert 0.0 < sig.fair_probability < 1.0
        assert sig.ev_pct > 0.0
        assert isinstance(sig.detected_at, datetime)

    def test_ev_formula_correctness(self):
        """ev_pct = ((offered_decimal * fair_prob) - 1) * 100."""
        from services.arb_detector import detect_ev

        records = _ev_records()
        # Use low threshold to capture all
        signals = asyncio.run(detect_ev(records, min_ev_pct=0.0))

        for sig in signals:
            expected_ev = ((sig.decimal_odds * sig.fair_probability) - 1) * 100
            assert abs(sig.ev_pct - expected_ev) < 0.01, (
                f"EV formula mismatch: {sig.ev_pct} vs {expected_ev}"
            )


class TestDetectEvNoOpportunity:
    def test_returns_empty_when_no_ev(self):
        """detect_ev returns [] when no EV exceeds threshold."""
        from services.arb_detector import detect_ev

        # Pass extremely high threshold
        records = _ev_records()
        signals = asyncio.run(detect_ev(records, min_ev_pct=50.0))
        assert signals == []

    def test_returns_empty_for_empty_input(self):
        """detect_ev returns [] for empty input."""
        from services.arb_detector import detect_ev

        signals = asyncio.run(detect_ev([], min_ev_pct=2.0))
        assert signals == []

    def test_respects_min_ev_threshold(self):
        """detect_ev correctly filters on min_ev_pct."""
        from services.arb_detector import detect_ev

        records = _ev_records()
        # Get signals at low threshold first
        all_signals = asyncio.run(detect_ev(records, min_ev_pct=0.0))
        if not all_signals:
            pytest.skip("No EV signals generated — test data may not produce EV")

        max_ev = max(s.ev_pct for s in all_signals)
        # Filter above max — should return []
        no_signals = asyncio.run(detect_ev(records, min_ev_pct=max_ev + 1.0))
        assert no_signals == []
