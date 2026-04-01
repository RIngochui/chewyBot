"""OddsApiAdapter — live and mock implementations for The Odds API v4.

Implements SportsbookAdapter interface with:
- Mock mode: reads mock/odds_api_sample.json fresh on every call (no API hit)
- Live mode: httpx.AsyncClient with exponential backoff (3 retries: 1s, 2s, 4s)
- Quota tracking: _quota_remaining updated from x-requests-remaining response header
- Graceful degradation: network failure after 3 retries returns [] (never raises)

References: ARB-01, ARB-02, ARB-03, ARB-04, ARB-05
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from adapters.base import SportsbookAdapter

logger = logging.getLogger(__name__)


class OddsApiAdapter(SportsbookAdapter):
    """The Odds API adapter. Implements SportsbookAdapter using https://the-odds-api.com

    Phase 3 implements full fetch logic with MOCK_MODE support, exponential backoff,
    and quota tracking from response headers (ARB-02, ARB-04, ARB-05, BOT-07).

    Books covered: fanduel, draftkings, betmgm, bet365 (ARB-03)
    """

    BASE_URL: str = "https://api.the-odds-api.com/v4"
    SUPPORTED_BOOKS: list[str] = ["fanduel", "draftkings", "betmgm", "bet365", "espnbet"]

    def __init__(self, api_key: str, mock_mode: bool = False) -> None:
        self.api_key = api_key
        self.mock_mode = mock_mode
        self._quota_remaining: int | None = None
        # Persistent async client: reuses TCP connections across the scan loop
        self._client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_with_retry(self, url: str, params: dict[str, Any]) -> httpx.Response | None:
        """Fetch URL with up to 3 attempts and exponential backoff (1s, 2s).

        Returns the response on success, or None after all attempts fail.
        Never raises — callers receive None to signal failure.
        """
        for attempt in range(3):
            try:
                resp = await self._client.get(url, params=params)
                resp.raise_for_status()
                return resp
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s
                else:
                    logger.warning(
                        "OddsApiAdapter: failed after 3 retries for %s: %s", url, exc
                    )
                    return None
        return None  # unreachable, satisfies type checker

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_sports(self) -> list[dict]:
        """Return available sports.

        Mock mode: returns [] — sports list not needed for mock scanning.
        Live mode: GET {BASE_URL}/sports with apiKey param.
        """
        if self.mock_mode:
            return []

        url = f"{self.BASE_URL}/sports"
        params: dict[str, Any] = {"apiKey": self.api_key}
        resp = await self._fetch_with_retry(url, params)
        if resp is None:
            return []
        return resp.json()  # type: ignore[no-any-return]

    async def get_events(self, sport_key: str) -> list[dict]:
        """Return events for a sport.

        Mock mode: returns [] — events are extracted from the odds response directly.
        Live mode: GET {BASE_URL}/sports/{sport_key}/events with apiKey param.
        """
        if self.mock_mode:
            return []

        url = f"{self.BASE_URL}/sports/{sport_key}/events"
        params: dict[str, Any] = {"apiKey": self.api_key}
        resp = await self._fetch_with_retry(url, params)
        if resp is None:
            return []
        return resp.json()  # type: ignore[no-any-return]

    async def get_odds(
        self,
        sport_key: str,
        regions: list[str],
        markets: list[str],
    ) -> list[dict]:
        """Return odds events for a sport/region/market combination.

        Mock mode:
          - Reads mock/odds_api_sample.json fresh on every call (catches dev edits).
          - _quota_remaining is NOT updated (no API hit).
          - Returns all events as list[dict] regardless of sport_key filter.

        Live mode:
          - GET {BASE_URL}/sports/{sport_key}/odds with required params.
          - Updates _quota_remaining from x-requests-remaining header on success.
          - Returns [] (does not raise) on failure after 3 retries.
        """
        if self.mock_mode:
            mock_path = Path("mock") / "odds_api_sample.json"
            with open(mock_path) as f:
                events = json.load(f)
            return [e for e in events if e.get("sport_key") == sport_key]

        url = f"{self.BASE_URL}/sports/{sport_key}/odds"
        params: dict[str, Any] = {
            "apiKey": self.api_key,
            "regions": ",".join(regions),
            "markets": ",".join(markets),
            "oddsFormat": "decimal",
            "bookmakers": ",".join(self.SUPPORTED_BOOKS),
        }
        resp = await self._fetch_with_retry(url, params)
        if resp is None:
            return []

        # Update quota from response header
        remaining = resp.headers.get("x-requests-remaining")
        if remaining is not None:
            try:
                self._quota_remaining = int(remaining)
            except ValueError:
                pass

        return resp.json()  # type: ignore[no-any-return]

    def get_quota_remaining(self) -> int | None:
        """Return last known API quota remaining from response headers."""
        return self._quota_remaining

    async def close(self) -> None:
        """Close the underlying httpx client for clean shutdown."""
        await self._client.aclose()
