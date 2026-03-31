"""Tests for OddsApiAdapter — mock mode and live API with exponential backoff.

TDD RED phase: tests written before implementation. All tests expected to fail initially.
"""
from __future__ import annotations

import json
import os
import sys
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.odds_api import OddsApiAdapter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_adapter(tmp_path, monkeypatch):
    """OddsApiAdapter in mock mode, pointing at a temp mock file."""
    sample = [
        {
            "id": "nba_lakers_warriors_20260401",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": "2026-04-01T02:00:00Z",
            "home_team": "Golden State Warriors",
            "away_team": "Los Angeles Lakers",
            "bookmakers": [
                {
                    "key": "fanduel",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Los Angeles Lakers", "price": 2.20},
                                {"name": "Golden State Warriors", "price": 1.75},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    mock_dir = tmp_path / "mock"
    mock_dir.mkdir()
    mock_file = mock_dir / "odds_api_sample.json"
    mock_file.write_text(json.dumps(sample))

    # Patch Path so that "mock/odds_api_sample.json" resolves to our temp file
    monkeypatch.chdir(tmp_path)

    adapter = OddsApiAdapter(api_key="test_key", mock_mode=True)
    return adapter, sample


@pytest.fixture
def live_adapter():
    """OddsApiAdapter in live mode."""
    return OddsApiAdapter(api_key="test_live_key", mock_mode=False)


# ---------------------------------------------------------------------------
# Mock mode tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_get_odds_returns_list(mock_adapter):
    """Mock mode: get_odds() returns a non-empty list of dicts."""
    adapter, sample = mock_adapter
    result = await adapter.get_odds("basketball_nba", ["us"], ["h2h"])
    assert isinstance(result, list)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_mock_get_odds_contains_bookmakers(mock_adapter):
    """Mock mode: returned events include 'bookmakers' key."""
    adapter, sample = mock_adapter
    result = await adapter.get_odds("basketball_nba", ["us"], ["h2h"])
    assert "bookmakers" in result[0]


@pytest.mark.asyncio
async def test_mock_get_odds_file_reloaded_each_call(mock_adapter, tmp_path):
    """Mock mode: file is reloaded on every call — edits during dev are picked up."""
    adapter, sample = mock_adapter

    # First call — 1 event
    result1 = await adapter.get_odds("basketball_nba", ["us"], ["h2h"])
    assert len(result1) == 1

    # Modify the file to add a second event
    updated = sample + [
        {
            "id": "extra_event_999",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": "2026-04-01T05:00:00Z",
            "home_team": "Team A",
            "away_team": "Team B",
            "bookmakers": [],
        }
    ]
    (tmp_path / "mock" / "odds_api_sample.json").write_text(json.dumps(updated))

    # Second call — should see updated file
    result2 = await adapter.get_odds("basketball_nba", ["us"], ["h2h"])
    assert len(result2) == 2


@pytest.mark.asyncio
async def test_mock_get_quota_remaining_is_none(mock_adapter):
    """Mock mode: quota remaining returns None (no API hit)."""
    adapter, _ = mock_adapter
    assert adapter.get_quota_remaining() is None
    # Still None after a call
    await adapter.get_odds("basketball_nba", ["us"], ["h2h"])
    assert adapter.get_quota_remaining() is None


@pytest.mark.asyncio
async def test_mock_get_sports_returns_empty_list(mock_adapter):
    """Mock mode: get_sports() returns []."""
    adapter, _ = mock_adapter
    result = await adapter.get_sports()
    assert result == []


@pytest.mark.asyncio
async def test_mock_get_events_returns_empty_list(mock_adapter):
    """Mock mode: get_events() returns []."""
    adapter, _ = mock_adapter
    result = await adapter.get_events("basketball_nba")
    assert result == []


# ---------------------------------------------------------------------------
# Live mode: correct URL and params
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_get_odds_calls_correct_url(live_adapter):
    """Live mode: get_odds calls the correct Odds API URL with required params."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "480"}
    mock_response.json.return_value = [{"id": "evt1", "bookmakers": []}]
    mock_response.raise_for_status = MagicMock()

    get_mock = AsyncMock(return_value=mock_response)
    with patch.object(live_adapter._client, "get", new=get_mock):
        result = await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    get_mock.assert_called_once()
    call_args = get_mock.call_args
    url = call_args[0][0] if call_args[0] else call_args.args[0]
    assert "basketball_nba" in url
    assert "the-odds-api.com" in url


@pytest.mark.asyncio
async def test_live_get_odds_sends_api_key(live_adapter):
    """Live mode: API key is sent in request params."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "480"}
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    get_mock = AsyncMock(return_value=mock_response)
    with patch.object(live_adapter._client, "get", new=get_mock):
        await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    call_kwargs = get_mock.call_args.kwargs
    params = call_kwargs.get("params", {})
    assert "apiKey" in params
    assert params["apiKey"] == "test_live_key"


@pytest.mark.asyncio
async def test_live_get_odds_sends_supported_books(live_adapter):
    """Live mode: all SUPPORTED_BOOKS are included in bookmakers param."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "480"}
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    get_mock = AsyncMock(return_value=mock_response)
    with patch.object(live_adapter._client, "get", new=get_mock):
        await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    call_kwargs = get_mock.call_args.kwargs
    params = call_kwargs.get("params", {})
    bookmakers_param = params.get("bookmakers", "")
    for book in OddsApiAdapter.SUPPORTED_BOOKS:
        assert book in bookmakers_param


# ---------------------------------------------------------------------------
# Live mode: quota tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_quota_updated_after_success(live_adapter):
    """Live mode: _quota_remaining is updated from x-requests-remaining header."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "456"}
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    assert live_adapter.get_quota_remaining() is None

    with patch.object(live_adapter._client, "get", new=AsyncMock(return_value=mock_response)):
        await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    assert live_adapter.get_quota_remaining() == 456


# ---------------------------------------------------------------------------
# Live mode: exponential backoff and failure handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_returns_empty_list_after_3_failures(live_adapter):
    """Live mode: returns [] after 3 consecutive failures, never raises."""
    import httpx

    with patch.object(
        live_adapter._client,
        "get",
        new=AsyncMock(side_effect=httpx.RequestError("connection refused")),
    ):
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    assert result == []


@pytest.mark.asyncio
async def test_live_retries_3_times_before_giving_up(live_adapter):
    """Live mode: exactly 3 attempts are made before returning []."""
    import httpx

    get_mock = AsyncMock(side_effect=httpx.RequestError("network error"))

    with patch.object(live_adapter._client, "get", new=get_mock):
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    assert get_mock.call_count == 3
    assert result == []


@pytest.mark.asyncio
async def test_live_backoff_sleeps_correct_durations(live_adapter):
    """Live mode: backoff sleeps 1s then 2s (attempt 0 and 1 before giving up on attempt 2)."""
    import httpx

    sleep_calls = []

    async def fake_sleep(duration):
        sleep_calls.append(duration)

    with patch.object(
        live_adapter._client,
        "get",
        new=AsyncMock(side_effect=httpx.RequestError("err")),
    ):
        with patch("asyncio.sleep", new=fake_sleep):
            await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    # Should sleep after attempt 0 (sleep 1s = 2^0) and after attempt 1 (sleep 2s = 2^1)
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 1
    assert sleep_calls[1] == 2


@pytest.mark.asyncio
async def test_live_succeeds_on_retry_after_transient_failure(live_adapter):
    """Live mode: succeeds if first attempt fails but second succeeds."""
    import httpx

    success_response = MagicMock()
    success_response.status_code = 200
    success_response.headers = {"x-requests-remaining": "479"}
    success_response.json.return_value = [{"id": "evt_retry", "bookmakers": []}]
    success_response.raise_for_status = MagicMock()

    call_results = [
        httpx.RequestError("timeout"),
        success_response,
    ]

    async def side_effect(*args, **kwargs):
        val = call_results.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    with patch.object(live_adapter._client, "get", new=AsyncMock(side_effect=side_effect)):
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await live_adapter.get_odds("basketball_nba", ["us"], ["h2h"])

    assert len(result) == 1
    assert result[0]["id"] == "evt_retry"
    assert live_adapter.get_quota_remaining() == 479


# ---------------------------------------------------------------------------
# Live mode: get_sports and get_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_get_sports_calls_api(live_adapter):
    """Live mode: get_sports() hits the /sports endpoint and returns the JSON list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "490"}
    mock_response.json.return_value = [{"key": "basketball_nba", "title": "NBA"}]
    mock_response.raise_for_status = MagicMock()

    get_mock = AsyncMock(return_value=mock_response)
    with patch.object(live_adapter._client, "get", new=get_mock):
        result = await live_adapter.get_sports()

    assert isinstance(result, list)
    assert result[0]["key"] == "basketball_nba"
    url = get_mock.call_args[0][0]
    assert "/sports" in url


@pytest.mark.asyncio
async def test_live_get_events_calls_api(live_adapter):
    """Live mode: get_events() hits the /sports/{sport_key}/events endpoint."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"x-requests-remaining": "489"}
    mock_response.json.return_value = [{"id": "evt1"}]
    mock_response.raise_for_status = MagicMock()

    get_mock = AsyncMock(return_value=mock_response)
    with patch.object(live_adapter._client, "get", new=get_mock):
        result = await live_adapter.get_events("basketball_nba")

    assert isinstance(result, list)
    url = get_mock.call_args[0][0]
    assert "basketball_nba" in url
    assert "events" in url


# ---------------------------------------------------------------------------
# Lifecycle: close()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_has_close_method(live_adapter):
    """Adapter exposes an async close() method for clean shutdown."""
    assert hasattr(live_adapter, "close")
    # Should not raise
    await live_adapter.close()


# ---------------------------------------------------------------------------
# Class attributes preserved
# ---------------------------------------------------------------------------


def test_class_attributes_preserved():
    """All required class vars and __init__ attrs must be present."""
    adapter = OddsApiAdapter(api_key="k", mock_mode=False)
    assert OddsApiAdapter.BASE_URL == "https://api.the-odds-api.com/v4"
    assert "fanduel" in OddsApiAdapter.SUPPORTED_BOOKS
    assert "draftkings" in OddsApiAdapter.SUPPORTED_BOOKS
    assert "betmgm" in OddsApiAdapter.SUPPORTED_BOOKS
    assert "bet365" in OddsApiAdapter.SUPPORTED_BOOKS
    assert adapter.api_key == "k"
    assert adapter.mock_mode is False
    assert adapter._quota_remaining is None
