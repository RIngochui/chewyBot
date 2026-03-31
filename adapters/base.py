from __future__ import annotations
from abc import ABC, abstractmethod


class SportsbookAdapter(ABC):
    """Abstract interface for sportsbook API adapters.

    Concrete implementations (e.g. OddsApiAdapter) must implement all three methods.
    This interface allows swapping sportsbook providers without touching scanner logic.
    """

    @abstractmethod
    async def get_sports(self) -> list[dict]:
        """Return list of available sports dicts from the sportsbook API."""
        ...

    @abstractmethod
    async def get_events(self, sport_key: str) -> list[dict]:
        """Return list of event dicts for a given sport_key."""
        ...

    @abstractmethod
    async def get_odds(
        self,
        sport_key: str,
        regions: list[str],
        markets: list[str],
    ) -> list[dict]:
        """Return list of odds dicts for the given sport, regions, and market types."""
        ...
