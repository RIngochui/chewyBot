"""Tracker data models."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional


@dataclass
class Route:
    """A tracked flight route."""

    id: int
    origin: str
    destination: str
    depart_date: date
    return_date: Optional[date]
    max_stops: int
    passengers: int
    cabin_class: str
    absolute_threshold_cad: Optional[float]
    active: bool
    created_at: datetime

    @classmethod
    def from_row(cls, row: Any) -> "Route":
        """Construct a Route from a sqlite3.Row."""
        return cls(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            depart_date=date.fromisoformat(row["depart_date"]),
            return_date=date.fromisoformat(row["return_date"]) if row["return_date"] else None,
            max_stops=row["max_stops"],
            passengers=row["passengers"],
            cabin_class=row["cabin_class"],
            absolute_threshold_cad=row["absolute_threshold_cad"],
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
