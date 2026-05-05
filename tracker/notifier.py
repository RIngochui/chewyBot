"""
Discord webhook notifier for flight price alerts.

Formats a Discord embed and POSTs it to the configured webhook URL.
Returns the Discord message ID so it can be stored in alerts_sent.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from tracker.models import Route
from tracker.serpapi_client import FlightResult

logger = logging.getLogger(__name__)

EMBED_COLOR = 0x2E7D32  # matches chewyBot's dark green


def _build_payload(route: Route, result: FlightResult) -> dict:
    """Build the Discord webhook payload with an alert embed."""
    stops_label = f"{result.stops} stop" + ("s" if result.stops != 1 else "")
    trip_label = (
        f"{route.depart_date} → {route.return_date}"
        if route.return_date
        else f"{route.depart_date} (one-way)"
    )

    return {
        "embeds": [
            {
                "title": "Flight Price Alert",
                "color": EMBED_COLOR,
                "fields": [
                    {
                        "name": "Route",
                        "value": f"{route.origin} → {route.destination}",
                        "inline": True,
                    },
                    {
                        "name": "Price",
                        "value": f"CAD {result.price_cad:,.2f}",
                        "inline": True,
                    },
                    {
                        "name": "Threshold",
                        "value": (
                            f"CAD {route.absolute_threshold_cad:,.2f}"
                            if route.absolute_threshold_cad
                            else "—"
                        ),
                        "inline": True,
                    },
                    {"name": "Carrier", "value": result.carrier, "inline": True},
                    {"name": "Stops", "value": stops_label, "inline": True},
                    {"name": "Dates", "value": trip_label, "inline": True},
                ],
                "footer": {"text": "Not financial advice"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }


def send_alert(route: Route, result: FlightResult, webhook_url: str) -> Optional[str]:
    """POST a price alert embed to a Discord webhook.

    Uses ?wait=true so Discord returns the message object, from which we
    extract and return the message ID. Returns None on failure (after logging).
    """
    payload = _build_payload(route, result)
    last_exc: Exception = RuntimeError("No attempts made")

    for attempt in range(3):
        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                params={"wait": "true"},
                timeout=10,
            )
            if resp.status_code >= 500:
                last_exc = requests.HTTPError(
                    f"Discord returned HTTP {resp.status_code}", response=resp
                )
                logger.warning("Discord webhook %d on attempt %d", resp.status_code, attempt + 1)
            else:
                resp.raise_for_status()
                return resp.json().get("id")
        except requests.ConnectionError as exc:
            last_exc = exc
            logger.warning("Webhook connection error on attempt %d: %s", attempt + 1, exc)
        if attempt < 2:
            time.sleep(2 ** attempt)

    logger.error("Failed to send webhook alert after 3 attempts: %s", last_exc)
    return None
