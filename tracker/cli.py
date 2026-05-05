"""
Flight tracker CLI.

Usage:
    python -m tracker <command> [options]

Run `python -m tracker --help` for the full command list.
"""

import sys
import logging
import logging.handlers
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click

from tracker.db import init_db, get_db
from tracker.models import Route
from tracker.queries import (
    DELETE_ROUTE,
    INSERT_PRICE_SNAPSHOT,
    INSERT_ROUTE,
    SELECT_ALL_ROUTES,
    SELECT_ROUTE_BY_ID,
    UPDATE_ROUTE_ACTIVE,
)

VALID_CABINS = ("ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST")

logger = logging.getLogger(__name__)


# ── Logging ────────────────────────────────────────────────────────────────────

def _setup_logging() -> None:
    """Configure WARNING+ to stdout and DEBUG+ to logs/tracker.log (5 MB × 3)."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.WARNING)
    stream.setFormatter(formatter)

    log_path = Path("logs/tracker.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    root.addHandler(stream)
    root.addHandler(fh)


# ── Validation helpers ─────────────────────────────────────────────────────────

def _validate_iata(value: str, param_hint: str) -> str:
    """Uppercase and validate a 3-letter IATA airport code."""
    code = value.upper().strip()
    if len(code) != 3 or not code.isalpha():
        raise click.BadParameter(
            f"'{code}' is not a valid 3-letter IATA code",
            param_hint=param_hint,
        )
    return code


def _validate_future_date(value: str, param_hint: str) -> date:
    """Parse YYYY-MM-DD and require the date to be strictly in the future."""
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise click.BadParameter(
            f"expected YYYY-MM-DD, got '{value}'",
            param_hint=param_hint,
        )
    if d <= date.today():
        raise click.BadParameter(
            f"must be a future date, got {value}",
            param_hint=param_hint,
        )
    return d


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _fmt_threshold(value: Optional[float]) -> str:
    return f"CAD {value:,.2f}" if value is not None else "—"


def _fmt_return(value: Optional[date]) -> str:
    return value.isoformat() if value else "one-way"


def _fmt_status(active: bool) -> str:
    return "ACTIVE" if active else "PAUSED"


# ── Shared lookup ──────────────────────────────────────────────────────────────

def _fetch_route(route_id: int) -> Route:
    """Return the Route for the given ID, or print an error and exit."""
    with get_db() as conn:
        row = conn.execute(SELECT_ROUTE_BY_ID, (route_id,)).fetchone()
    if row is None:
        click.echo(f"Error: route {route_id} not found.", err=True)
        raise SystemExit(1)
    return Route.from_row(row)


# ── CLI group ──────────────────────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """Flight price tracker — manage routes from the command line."""
    _setup_logging()
    init_db()


# ── add ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("origin")
@click.argument("destination")
@click.option("--depart", required=True, metavar="YYYY-MM-DD", help="Departure date.")
@click.option(
    "--return", "return_date", default=None, metavar="YYYY-MM-DD",
    help="Return date. Omit for one-way.",
)
@click.option("--max-stops", default=1, show_default=True, type=int, help="Maximum stops allowed.")
@click.option("--passengers", default=1, show_default=True, type=int, help="Number of passengers.")
@click.option(
    "--cabin", default="ECONOMY", show_default=True,
    type=click.Choice(VALID_CABINS, case_sensitive=False),
    help="Cabin class.",
)
@click.option(
    "--threshold", default=None, type=float, metavar="AMOUNT",
    help="Alert when cheapest price drops below this amount (CAD).",
)
def add(
    origin: str,
    destination: str,
    depart: str,
    return_date: Optional[str],
    max_stops: int,
    passengers: int,
    cabin: str,
    threshold: Optional[float],
) -> None:
    """Add a new flight route to watch.

    ORIGIN and DESTINATION are 3-letter IATA codes (e.g. YYZ, LHR).
    """
    origin = _validate_iata(origin, "ORIGIN")
    destination = _validate_iata(destination, "DESTINATION")
    depart_dt = _validate_future_date(depart, "--depart")

    return_dt: Optional[date] = None
    if return_date is not None:
        return_dt = _validate_future_date(return_date, "--return")
        if return_dt <= depart_dt:
            raise click.BadParameter(
                "return date must be after departure date",
                param_hint="--return",
            )

    if threshold is not None and threshold <= 0:
        raise click.BadParameter("must be a positive number", param_hint="--threshold")

    if passengers < 1:
        raise click.BadParameter("must be at least 1", param_hint="--passengers")

    if max_stops < 0:
        raise click.BadParameter("cannot be negative", param_hint="--max-stops")

    with get_db() as conn:
        cursor = conn.execute(
            INSERT_ROUTE,
            (
                origin,
                destination,
                depart_dt.isoformat(),
                return_dt.isoformat() if return_dt else None,
                max_stops,
                passengers,
                cabin.upper(),
                threshold,
            ),
        )
        route_id = cursor.lastrowid

    arrow = "⇄" if return_dt else "→"
    click.echo(
        f"Added route #{route_id}: {origin} {arrow} {destination}, depart {depart_dt}"
        + (f", return {return_dt}" if return_dt else " (one-way)")
        + "."
    )
    logger.info("Added route #%d: %s -> %s", route_id, origin, destination)


# ── list ───────────────────────────────────────────────────────────────────────

@cli.command("list")
def list_routes() -> None:
    """List all tracked routes (active and paused)."""
    with get_db() as conn:
        rows = conn.execute(SELECT_ALL_ROUTES).fetchall()

    if not rows:
        click.echo("No routes tracked yet. Use 'tracker add' to get started.")
        return

    W = {
        "id": 4, "route": 8, "depart": 10, "ret": 10,
        "stops": 5, "pax": 3, "cabin": 17, "threshold": 17, "status": 6,
    }

    def line(id_: str, route: str, dep: str, ret: str, stops: str,
             pax: str, cabin: str, thresh: str, status: str) -> str:
        return (
            f"{id_:>{W['id']}}  {route:<{W['route']}}  {dep:<{W['depart']}}  "
            f"{ret:<{W['ret']}}  {stops:>{W['stops']}}  {pax:>{W['pax']}}  "
            f"{cabin:<{W['cabin']}}  {thresh:>{W['threshold']}}  {status}"
        )

    header = line(
        "ID", "ROUTE", "DEPART", "RETURN", "STOPS", "PAX",
        "CABIN", "THRESHOLD (CAD)", "STATUS",
    )
    click.echo(header)
    click.echo("─" * len(header))

    for r in rows:
        route_str = f"{r['origin']}→{r['destination']}"
        ret_date = date.fromisoformat(r["return_date"]) if r["return_date"] else None
        click.echo(line(
            str(r["id"]),
            route_str,
            r["depart_date"],
            _fmt_return(ret_date),
            str(r["max_stops"]),
            str(r["passengers"]),
            r["cabin_class"],
            _fmt_threshold(r["absolute_threshold_cad"]),
            _fmt_status(bool(r["active"])),
        ))


# ── show ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("route_id", type=int, metavar="ID")
def show(route_id: int) -> None:
    """Show full details for a single route."""
    route = _fetch_route(route_id)

    trip = "Round trip" if route.return_date else "One-way"
    click.echo(f"\nRoute #{route.id}: {route.origin} → {route.destination}")
    click.echo(f"  Trip:        {trip}")
    click.echo(f"  Depart:      {route.depart_date}")
    if route.return_date:
        click.echo(f"  Return:      {route.return_date}")
    click.echo(f"  Max stops:   {route.max_stops}")
    click.echo(f"  Passengers:  {route.passengers}")
    click.echo(f"  Cabin:       {route.cabin_class}")
    click.echo(f"  Threshold:   {_fmt_threshold(route.absolute_threshold_cad)}")
    click.echo(f"  Status:      {_fmt_status(route.active)}")
    click.echo(f"  Created:     {route.created_at}\n")


# ── remove ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("route_id", type=int, metavar="ID")
def remove(route_id: int) -> None:
    """Delete a route (prompts for confirmation)."""
    route = _fetch_route(route_id)
    click.confirm(
        f"Delete route #{route_id} ({route.origin}→{route.destination}, "
        f"depart {route.depart_date})?",
        abort=True,
    )
    with get_db() as conn:
        conn.execute(DELETE_ROUTE, (route_id,))
    click.echo(f"Removed route #{route_id}.")
    logger.info("Removed route #%d", route_id)


# ── pause ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("route_id", type=int, metavar="ID")
def pause(route_id: int) -> None:
    """Pause polling for a route."""
    route = _fetch_route(route_id)
    if not route.active:
        click.echo(f"Route #{route_id} is already paused.")
        return
    with get_db() as conn:
        conn.execute(UPDATE_ROUTE_ACTIVE, (0, route_id))
    click.echo(f"Paused route #{route_id} ({route.origin}→{route.destination}).")
    logger.info("Paused route #%d", route_id)


# ── resume ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("route_id", type=int, metavar="ID")
def resume(route_id: int) -> None:
    """Resume polling for a paused route."""
    route = _fetch_route(route_id)
    if route.active:
        click.echo(f"Route #{route_id} is already active.")
        return
    with get_db() as conn:
        conn.execute(UPDATE_ROUTE_ACTIVE, (1, route_id))
    click.echo(f"Resumed route #{route_id} ({route.origin}→{route.destination}).")
    logger.info("Resumed route #%d", route_id)


# ── poll ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("route_id", type=int, metavar="ID")
def poll(route_id: int) -> None:
    """Fetch the current cheapest price for a route and save it."""
    from tracker import serpapi_client

    route = _fetch_route(route_id)
    if not route.active:
        click.echo(f"Route #{route_id} is paused. Use 'tracker resume {route_id}' first.")
        return

    dates = f"{route.depart_date}"
    if route.return_date:
        dates += f" → {route.return_date}"
    click.echo(f"Polling route #{route_id}: {route.origin} → {route.destination} ({dates}) ...")

    result = None
    success = False
    try:
        result = serpapi_client.search(route)
        success = True
    except Exception as exc:
        click.echo(f"Poll failed: {exc}", err=True)

    with get_db() as conn:
        cursor = conn.execute(
            INSERT_PRICE_SNAPSHOT,
            (
                route_id,
                result.price_cad if result else None,
                result.price_cad if result else None,
                "CAD",
                result.carrier if result else None,
                result.stops if result else None,
                result.offer_json if result else None,
                1 if success else 0,
            ),
        )
        snapshot_id = cursor.lastrowid

    if result:
        stops_label = f"{result.stops} stop" + ("s" if result.stops != 1 else "")
        click.echo(
            f"Cheapest: CAD {result.price_cad:,.2f} via {result.carrier} ({stops_label})"
        )
        click.echo(f"Saved to price_snapshots (id={snapshot_id}).")
        logger.info(
            "Poll #%d: CAD %.2f via %s (%d stop(s))",
            route_id, result.price_cad, result.carrier, result.stops,
        )
    else:
        click.echo(f"No flights found. Saved failed snapshot (id={snapshot_id}).")
        logger.warning("Poll #%d: no results or request failed", route_id)
