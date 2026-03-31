"""Tests for services/odds_normalizer.py — TDD RED phase (03-03)."""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime

from services.odds_normalizer import normalize


# Minimal single-bookmaker event matching the plan's spec example
SINGLE_BOOK_EVENT = {
    "id": "nba_lakers_warriors_20260401",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2026-04-01T02:00:00Z",
    "home_team": "Golden State Warriors",
    "away_team": "Los Angeles Lakers",
    "bookmakers": [
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2026-03-30T18:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "last_update": "2026-03-30T18:00:00Z",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 2.20},
                        {"name": "Golden State Warriors", "price": 1.75},
                    ],
                }
            ],
        }
    ],
}

# Multi-bookmaker event with spreads (point field present)
MULTI_BOOK_EVENT = {
    "id": "nba_lakers_warriors_20260401",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2026-04-01T02:00:00Z",
    "home_team": "Golden State Warriors",
    "away_team": "Los Angeles Lakers",
    "bookmakers": [
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2026-03-30T18:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 2.20},
                        {"name": "Golden State Warriors", "price": 1.75},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.91, "point": 3.5},
                        {"name": "Golden State Warriors", "price": 1.91, "point": -3.5},
                    ],
                },
            ],
        },
        {
            "key": "draftkings",
            "title": "DraftKings",
            "last_update": "2026-03-30T18:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Los Angeles Lakers", "price": 1.65},
                        {"name": "Golden State Warriors", "price": 2.25},
                    ],
                },
            ],
        },
    ],
}

NO_BOOKMAKERS_EVENT = {
    "id": "nba_empty",
    "sport_key": "basketball_nba",
    "sport_title": "NBA",
    "commence_time": "2026-04-01T02:00:00Z",
    "home_team": "Golden State Warriors",
    "away_team": "Los Angeles Lakers",
    "bookmakers": [],
}


def run(coro):
    return asyncio.run(coro)


class TestNormalizeRecordCount:
    """normalize() returns one record per (bookmaker, market, outcome)."""

    def test_single_book_h2h_two_outcomes(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        # 1 book * 1 market * 2 outcomes = 2
        assert len(results) == 2

    def test_multi_book_multi_market(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA"))
        # fanduel h2h: 2 + fanduel spreads: 2 + draftkings h2h: 2 = 6
        assert len(results) == 6

    def test_no_bookmakers_returns_empty(self):
        results = run(normalize(NO_BOOKMAKERS_EVENT, "basketball_nba", "NBA"))
        assert results == []


class TestEventId:
    """event_id uses home_away_YYYYMMDD slug format (ARB-07)."""

    def test_event_id_format(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        # home=Golden State Warriors, away=Los Angeles Lakers, date=20260401
        assert results[0].event_id == "golden_state_warriors_los_angeles_lakers_20260401"

    def test_all_records_share_same_event_id(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA"))
        event_ids = {r.event_id for r in results}
        assert len(event_ids) == 1, "All records from same event must share event_id"

    def test_event_id_lowercased(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        assert results[0].event_id == results[0].event_id.lower()


class TestMarketKey:
    """market_key is unique per (book, market, outcome)."""

    def test_market_key_format_lakers_h2h_fanduel(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        event_id = "golden_state_warriors_los_angeles_lakers_20260401"
        lakers_record = next(r for r in results if "los_angeles_lakers" in r.market_key and "fanduel" not in r.market_key or
                             (r.selection_name == "Los Angeles Lakers"))
        # market_key = {event_id}_h2h_los_angeles_lakers
        assert lakers_record.market_key == f"{event_id}_h2h_los_angeles_lakers"

    def test_market_keys_unique_within_same_bookmaker(self):
        # market_key encodes event+market_type+selection — unique within a single book's records
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA"))
        fanduel_records = [r for r in results if r.book_name == "fanduel"]
        market_keys = [r.market_key for r in fanduel_records]
        assert len(market_keys) == len(set(market_keys)), "market_keys must be unique within same book"

    def test_market_key_contains_event_id(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.market_key.startswith(r.event_id)


class TestDecimalOdds:
    """decimal_odds matches the price field exactly."""

    def test_decimal_odds_from_price(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        prices = {r.decimal_odds for r in results}
        assert 2.20 in prices
        assert 1.75 in prices

    def test_decimal_odds_greater_than_one(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.decimal_odds > 1.0


class TestAmericanOdds:
    """american_odds is derived via decimal_to_american."""

    def test_american_odds_derived(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        # price 2.20 -> decimal >= 2.0 -> round((2.20 - 1) * 100) = 120
        lakers = next(r for r in results if r.decimal_odds == 2.20)
        assert lakers.american_odds == 120

    def test_american_odds_negative_for_favorite(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        # price 1.75 -> decimal < 2.0 -> round(-100 / (1.75 - 1)) = round(-133.3) = -133
        warriors = next(r for r in results if r.decimal_odds == 1.75)
        assert warriors.american_odds == -133


class TestLineValue:
    """line_value populated from 'point' field when present, None otherwise."""

    def test_line_value_none_when_no_point(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        # h2h market has no 'point' field
        for r in results:
            assert r.line_value is None

    def test_line_value_from_point_field(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA"))
        spreads_records = [r for r in results if r.market_type == "spreads"]
        assert len(spreads_records) == 2
        line_values = {r.line_value for r in spreads_records}
        assert 3.5 in line_values
        assert -3.5 in line_values


class TestOtherFields:
    """Other NormalizedOdds fields populated correctly."""

    def test_event_name_format(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        assert results[0].event_name == "Los Angeles Lakers @ Golden State Warriors"

    def test_start_time_parsed_from_commence_time(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        assert results[0].start_time == datetime.fromisoformat("2026-04-01T02:00:00+00:00")

    def test_book_name_is_bookmaker_key(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.book_name == "fanduel"

    def test_sport_from_sport_key_param(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.sport == "basketball_nba"

    def test_league_from_league_param(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.league == "NBA"

    def test_home_team_away_team_populated(self):
        results = run(normalize(SINGLE_BOOK_EVENT, "basketball_nba", "NBA"))
        for r in results:
            assert r.home_team == "Golden State Warriors"
            assert r.away_team == "Los Angeles Lakers"


class TestSupportedBooksFilter:
    """When supported_books provided, only matching bookmakers included."""

    def test_filter_to_supported_books(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA", supported_books=["fanduel"]))
        for r in results:
            assert r.book_name == "fanduel"

    def test_filter_empty_list_returns_empty(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA", supported_books=[]))
        assert results == []

    def test_no_filter_includes_all_books(self):
        results = run(normalize(MULTI_BOOK_EVENT, "basketball_nba", "NBA", supported_books=None))
        books = {r.book_name for r in results}
        assert "fanduel" in books
        assert "draftkings" in books
