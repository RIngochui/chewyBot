from __future__ import annotations
import httpx
from adapters.base import SportsbookAdapter


class OddsApiAdapter(SportsbookAdapter):
    """The Odds API adapter. Implements SportsbookAdapter using https://the-odds-api.com

    Phase 3 implements full fetch logic with MOCK_MODE support, exponential backoff,
    and quota tracking from response headers (ARB-02, ARB-04, ARB-05, BOT-07).

    Books covered: fanduel, draftkings, betmgm, bet365 (ARB-03)
    """

    BASE_URL: str = "https://api.the-odds-api.com/v4"
    SUPPORTED_BOOKS: list[str] = ["fanduel", "draftkings", "betmgm", "bet365"]

    def __init__(self, api_key: str, mock_mode: bool = False) -> None:
        self.api_key = api_key
        self.mock_mode = mock_mode
        self._quota_remaining: int | None = None

    async def get_sports(self) -> list[dict]:
        """Fetch available sports. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_sports() — implement in Phase 3")

    async def get_events(self, sport_key: str) -> list[dict]:
        """Fetch events for a sport. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_events() — implement in Phase 3")

    async def get_odds(
        self,
        sport_key: str,
        regions: list[str],
        markets: list[str],
    ) -> list[dict]:
        """Fetch odds for a sport. Phase 3 implementation."""
        raise NotImplementedError("OddsApiAdapter.get_odds() — implement in Phase 3")

    def get_quota_remaining(self) -> int | None:
        """Return last known API quota remaining from response headers."""
        return self._quota_remaining
