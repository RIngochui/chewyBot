"""
Flight tracker polling scheduler.

Provides:
  - poll_all_routes() — one poll round across all active routes
  - run_daemon()      — loops forever, calling poll_all_routes() on an interval

Threshold breaches are detected here and logged/printed. Discord webhook
delivery is handled in Session 4 (tracker/notifier.py).
"""

import logging
import time
from datetime import datetime

import click

from tracker.db import get_db
from tracker.models import Route
from tracker.queries import INSERT_PRICE_SNAPSHOT, SELECT_ALL_ACTIVE_ROUTES
from tracker import serpapi_client

logger = logging.getLogger(__name__)


def _poll_route(route: Route) -> None:
    """Poll one route, save a snapshot, and log any threshold breach."""
    result = None
    success = False
    try:
        result = serpapi_client.search(route)
        success = True
    except Exception as exc:
        logger.error(
            "Poll failed for route #%d (%s→%s): %s",
            route.id, route.origin, route.destination, exc,
        )

    with get_db() as conn:
        conn.execute(
            INSERT_PRICE_SNAPSHOT,
            (
                route.id,
                result.price_cad if result else None,
                result.price_cad if result else None,
                "CAD",
                result.carrier if result else None,
                result.stops if result else None,
                result.offer_json if result else None,
                1 if success else 0,
            ),
        )

    if result:
        stops_label = f"{result.stops} stop" + ("s" if result.stops != 1 else "")
        click.echo(
            f"  #{route.id} {route.origin}→{route.destination}: "
            f"CAD {result.price_cad:,.2f} via {result.carrier} ({stops_label})"
        )
        logger.info(
            "Route #%d: CAD %.2f via %s (%d stop(s))",
            route.id, result.price_cad, result.carrier, result.stops,
        )

        if route.absolute_threshold_cad and result.price_cad < route.absolute_threshold_cad:
            click.echo(
                f"  [ALERT] #{route.id} {route.origin}→{route.destination}: "
                f"CAD {result.price_cad:,.2f} is below your threshold of "
                f"CAD {route.absolute_threshold_cad:,.2f}"
            )
            logger.warning(
                "THRESHOLD BREACH route #%d: CAD %.2f < CAD %.2f",
                route.id, result.price_cad, route.absolute_threshold_cad,
            )
    else:
        click.echo(f"  #{route.id} {route.origin}→{route.destination}: no results")
        logger.warning("Route #%d: poll returned no results", route.id)


def poll_all_routes() -> int:
    """Poll every active route once. Returns the number of routes polled."""
    with get_db() as conn:
        rows = conn.execute(SELECT_ALL_ACTIVE_ROUTES).fetchall()

    routes = [Route.from_row(r) for r in rows]
    if not routes:
        click.echo("No active routes to poll.")
        return 0

    click.echo(f"Polling {len(routes)} active route(s)...")
    for route in routes:
        _poll_route(route)
    return len(routes)


def run_daemon(interval_hours: float) -> None:
    """Poll all active routes on a fixed interval until Ctrl+C.

    Polls immediately on startup, then sleeps between rounds.
    """
    click.echo(f"Tracker daemon started. Polling every {interval_hours:g}h. Press Ctrl+C to stop.")
    logger.info("Daemon started, interval=%.1fh", interval_hours)

    interval_secs = interval_hours * 3600
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"\n[{now}] Poll round starting...")
        poll_all_routes()
        click.echo(f"Next poll in {interval_hours:g}h.")
        time.sleep(interval_secs)
