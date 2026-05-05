"""
Serpapi Google Flights client.

Searches for the cheapest flight for a route using the Serpapi Google Flights
engine. No SDK — plain GET with requests (already in requirements.txt).
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from tracker.config import config
from tracker.models import Route

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search"

_CABIN_MAP: dict[str, int] = {
    "ECONOMY": 1,
    "PREMIUM_ECONOMY": 2,
    "BUSINESS": 3,
    "FIRST": 4,
}


@dataclass
class FlightResult:
    """Parsed result from a Serpapi Google Flights search."""

    price_cad: float
    carrier: str
    stops: int
    offer_json: str  # raw JSON of the cheapest offer, stored in price_snapshots


def _stops_param(max_stops: int) -> int:
    """Map max_stops to Serpapi's stops filter value."""
    # Serpapi: 0=any, 1=nonstop only, 2=1 stop or fewer, 3=2 stops or fewer
    if max_stops == 0:
        return 1
    if max_stops == 1:
        return 2
    if max_stops == 2:
        return 3
    return 0


def _build_params(route: Route) -> dict:
    """Build the Serpapi query parameter dict for a route."""
    params: dict = {
        "engine": "google_flights",
        "departure_id": route.origin,
        "arrival_id": route.destination,
        "outbound_date": route.depart_date.isoformat(),
        "currency": "CAD",
        "hl": "en",
        "gl": "ca",
        "adults": route.passengers,
        "travel_class": _CABIN_MAP.get(route.cabin_class, 1),
        "stops": _stops_param(route.max_stops),
        "api_key": config.SERPAPI_KEY,
    }
    if route.return_date:
        params["return_date"] = route.return_date.isoformat()
    else:
        params["type"] = 2  # one-way
    return params


def _parse_cheapest(data: dict) -> Optional[FlightResult]:
    """Extract the cheapest offer from a Google Flights response.

    Checks both best_flights and other_flights; picks the lowest price.
    Returns None if no priced offers are present.
    """
    candidates = [
        offer
        for key in ("best_flights", "other_flights")
        for offer in data.get(key, [])
        if offer.get("price") is not None
    ]

    if not candidates:
        return None

    cheapest = min(candidates, key=lambda o: o["price"])
    flights = cheapest.get("flights", [])
    carrier = flights[0].get("airline", "Unknown") if flights else "Unknown"
    stops = max(0, len(flights) - 1)

    return FlightResult(
        price_cad=float(cheapest["price"]),
        carrier=carrier,
        stops=stops,
        offer_json=json.dumps(cheapest),
    )


def _get_with_backoff(params: dict) -> dict:
    """GET Serpapi with exponential backoff: 3 attempts, 1 s / 2 s delays."""
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(3):
        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=30)
            if resp.status_code >= 500:
                last_exc = requests.HTTPError(
                    f"Serpapi returned HTTP {resp.status_code}", response=resp
                )
                logger.warning("Serpapi %d on attempt %d", resp.status_code, attempt + 1)
            else:
                resp.raise_for_status()
                return resp.json()
        except requests.ConnectionError as exc:
            last_exc = exc
            logger.warning("Connection error on attempt %d: %s", attempt + 1, exc)
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise last_exc


def search(route: Route) -> Optional[FlightResult]:
    """Search for the cheapest flight price for a route.

    Returns a FlightResult on success, or None if the response contains no
    priced offers. Raises after 3 failed attempts (5xx or connection error).
    """
    params = _build_params(route)
    logger.debug(
        "Serpapi search: %s → %s on %s", route.origin, route.destination, route.depart_date
    )
    data = _get_with_backoff(params)

    if "error" in data:
        raise RuntimeError(f"Serpapi error: {data['error']}")

    result = _parse_cheapest(data)
    if result:
        logger.debug(
            "Cheapest: CAD %.2f via %s (%d stop(s))",
            result.price_cad, result.carrier, result.stops,
        )
    else:
        logger.debug("No priced offers in response")

    return result
