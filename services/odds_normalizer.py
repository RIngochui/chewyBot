from __future__ import annotations
from models.odds import OddsSnapshot, NormalizedOdds


async def normalize(snapshot: OddsSnapshot) -> list[NormalizedOdds]:
    """Normalize a raw OddsSnapshot into canonical NormalizedOdds records.

    Implements ARB-06 canonical schema and ARB-07 key generation:
      event_id: "{home_team}_{away_team}_{date}"
      market_key: "{event_id}_{market_type}_{selection_name}"

    Phase 3 full implementation.
    """
    raise NotImplementedError("odds_normalizer.normalize() — implement in Phase 3")
