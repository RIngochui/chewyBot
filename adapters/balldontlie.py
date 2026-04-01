"""BallDontLieAdapter — live and mock implementations for balldontlie.io API v1.

Provides:
- Mock mode: reads mock/balldontlie_sample.json on every call (no API hit)
- Live mode: httpx.AsyncClient with exponential backoff (3 retries: 1s, 2s)
- Rate limit: 5 req/min (free tier) — callers must sleep 12s between calls
- Graceful degradation: all failures return [] (never raises)

References: PAR-01, BOT-06, BOT-07
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_MOCK_PATH = Path("mock") / "balldontlie_sample.json"


class BallDontLieAdapter:
    """balldontlie.io adapter. Provides NBA game results and team season averages.

    Free tier is keyless — no API key required.
    Rate limit: 5 requests/min (enforced by callers via asyncio.sleep(12)).

    Endpoints used (free tier only):
    - /v1/games — recent game results (W/L), schedule, home/away game log
    - /v1/team_season_averages/general — season home/away splits per team

    References: PAR-01, decision E from CONTEXT.md, BOT-07.
    """

    BASE_URL: str = "https://api.balldontlie.io/v1"

    def __init__(self, mock_mode: bool = False) -> None:
        self.mock_mode = mock_mode
        self._client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_with_retry(self, url: str, params: dict[str, Any]) -> httpx.Response | None:
        """Fetch URL with up to 3 attempts and exponential backoff (1s, 2s).

        Returns the response on success, or None after all attempts fail.
        Never raises — callers receive None to signal failure. (BOT-07)
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
                        "BallDontLieAdapter: failed after 3 retries for %s: %s", url, exc
                    )
                    return None
        return None  # unreachable, satisfies type checker

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_games(
        self,
        team_ids: list[int] | None = None,
        dates: list[str] | None = None,
        seasons: list[int] | None = None,
        per_page: int = 100,
    ) -> list[dict]:
        """Fetch games from /v1/games. Returns list of game dicts.

        Mock mode: reads mock/balldontlie_sample.json, returns data["recent_games"].
        Live mode: GET BASE_URL/games with params (team_ids[], dates[], seasons[],
        per_page). Handles cursor-based pagination — follows meta.next_cursor until
        exhausted. Max 2 pages to stay within rate limits.
        Params with list values passed as repeated keys (httpx handles list params).
        Returns [] on any error.
        """
        if self.mock_mode:
            try:
                with open(_MOCK_PATH) as f:
                    data = json.load(f)
                return data.get("recent_games", [])
            except Exception as exc:
                logger.warning("BallDontLieAdapter: failed to load mock games: %s", exc)
                return []

        url = f"{self.BASE_URL}/games"
        params: dict[str, Any] = {"per_page": per_page}
        if team_ids:
            params["team_ids[]"] = team_ids
        if dates:
            params["dates[]"] = dates
        if seasons:
            params["seasons[]"] = seasons

        all_games: list[dict] = []
        pages_fetched = 0
        next_cursor: int | None = None

        while pages_fetched < 2:
            if next_cursor is not None:
                params["cursor"] = next_cursor

            resp = await self._fetch_with_retry(url, params)
            if resp is None:
                break

            payload = resp.json()
            games = payload.get("data", [])
            all_games.extend(games)
            pages_fetched += 1

            meta = payload.get("meta", {})
            next_cursor = meta.get("next_cursor")
            if next_cursor is None:
                break

            # Rate limit: free tier is 5 req/min; sleep before next page request
            await asyncio.sleep(12)

        return all_games

    async def get_team_season_averages(
        self,
        season: int,
        team_ids: list[int] | None = None,
    ) -> list[dict]:
        """Fetch team season averages from /v1/team_season_averages/general.

        NOTE: endpoint is /team_season_averages/general (NOT /team_stats — does not
        exist in free tier per RESEARCH.md decision E). Category param = "general".

        Mock mode: reads mock/balldontlie_sample.json, returns data["team_stats"]
        (mock file uses "team_stats" key for this data).
        Live mode: GET BASE_URL/team_season_averages/general?season=N&team_ids[]=X
        Returns [] on any error.
        """
        if self.mock_mode:
            try:
                with open(_MOCK_PATH) as f:
                    data = json.load(f)
                # Mock file uses "team_stats" key for team season average data
                return data.get("team_stats", [])
            except Exception as exc:
                logger.warning(
                    "BallDontLieAdapter: failed to load mock team season averages: %s", exc
                )
                return []

        url = f"{self.BASE_URL}/team_season_averages/general"
        params: dict[str, Any] = {"season": season, "category": "general"}
        if team_ids:
            params["team_ids[]"] = team_ids

        resp = await self._fetch_with_retry(url, params)
        if resp is None:
            return []

        payload = resp.json()
        return payload.get("data", [])

    async def close(self) -> None:
        """Close the underlying httpx client for clean shutdown."""
        await self._client.aclose()
