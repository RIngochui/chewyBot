"""
Flight price tracker Discord cog.

Slash commands under /tracker for managing routes and triggering manual polls.
All responses are ephemeral — only the invoking user sees them.
The polling daemon (python -m tracker run) handles scheduled polling;
these commands let you manage everything from Discord.
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import EMBED_COLOR
from tracker.config import config as tracker_config
from tracker.db import get_db, init_db
from tracker.models import Route
from tracker.queries import (
    DELETE_ROUTE,
    INSERT_PRICE_SNAPSHOT,
    INSERT_ROUTE,
    SELECT_ALL_ROUTES,
    SELECT_ROUTE_BY_ID,
    UPDATE_ROUTE_ACTIVE,
)

logger = logging.getLogger(__name__)

_CABIN_CHOICES = [
    app_commands.Choice(name="Economy", value="ECONOMY"),
    app_commands.Choice(name="Premium Economy", value="PREMIUM_ECONOMY"),
    app_commands.Choice(name="Business", value="BUSINESS"),
    app_commands.Choice(name="First", value="FIRST"),
]


class TrackerCog(commands.Cog):
    """Flight price tracker slash commands."""

    tracker = app_commands.Group(
        name="tracker", description="Flight price tracker commands"
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        await asyncio.to_thread(init_db)

    # ── /tracker list ──────────────────────────────────────────────────────────

    @tracker.command(name="list")
    async def tracker_list(self, interaction: discord.Interaction) -> None:
        """List all tracked flight routes."""
        def _query():
            with get_db() as conn:
                return conn.execute(SELECT_ALL_ROUTES).fetchall()

        rows = await asyncio.to_thread(_query)

        if not rows:
            await interaction.response.send_message(
                "No routes tracked yet. Use `/tracker add` to get started.",
                ephemeral=True,
            )
            return

        lines = []
        for r in rows:
            status = "✅" if r["active"] else "⏸️"
            threshold = (
                f"CAD {r['absolute_threshold_cad']:,.0f}"
                if r["absolute_threshold_cad"]
                else "—"
            )
            ret = f" → `{r['return_date']}`" if r["return_date"] else ""
            lines.append(
                f"{status} **#{r['id']}** {r['origin']}→{r['destination']}  "
                f"`{r['depart_date']}`{ret}  threshold: {threshold}"
            )

        embed = discord.Embed(
            title="Tracked Flight Routes",
            description="\n".join(lines),
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /tracker add ───────────────────────────────────────────────────────────

    @tracker.command(name="add")
    @app_commands.describe(
        origin="Departure airport (3-letter IATA code, e.g. YYZ)",
        destination="Arrival airport (3-letter IATA code, e.g. LHR)",
        depart="Departure date (YYYY-MM-DD)",
        return_date="Return date (YYYY-MM-DD) — omit for one-way",
        max_stops="Maximum number of stops (default 1)",
        passengers="Number of passengers (default 1)",
        cabin="Cabin class (default Economy)",
        threshold="Alert if price drops below this CAD amount",
    )
    @app_commands.choices(cabin=_CABIN_CHOICES)
    async def tracker_add(
        self,
        interaction: discord.Interaction,
        origin: str,
        destination: str,
        depart: str,
        return_date: Optional[str] = None,
        max_stops: int = 1,
        passengers: int = 1,
        cabin: str = "ECONOMY",
        threshold: Optional[float] = None,
    ) -> None:
        """Add a new flight route to watch."""
        origin = origin.upper().strip()
        destination = destination.upper().strip()

        if len(origin) != 3 or not origin.isalpha():
            await interaction.response.send_message(
                f"❌ `{origin}` is not a valid 3-letter IATA code.", ephemeral=True
            )
            return
        if len(destination) != 3 or not destination.isalpha():
            await interaction.response.send_message(
                f"❌ `{destination}` is not a valid 3-letter IATA code.", ephemeral=True
            )
            return

        try:
            depart_dt = datetime.strptime(depart, "%Y-%m-%d").date()
        except ValueError:
            await interaction.response.send_message(
                "❌ Departure date must be YYYY-MM-DD.", ephemeral=True
            )
            return
        if depart_dt <= date.today():
            await interaction.response.send_message(
                "❌ Departure date must be in the future.", ephemeral=True
            )
            return

        return_dt: Optional[date] = None
        if return_date:
            try:
                return_dt = datetime.strptime(return_date, "%Y-%m-%d").date()
            except ValueError:
                await interaction.response.send_message(
                    "❌ Return date must be YYYY-MM-DD.", ephemeral=True
                )
                return
            if return_dt <= depart_dt:
                await interaction.response.send_message(
                    "❌ Return date must be after departure date.", ephemeral=True
                )
                return

        if threshold is not None and threshold <= 0:
            await interaction.response.send_message(
                "❌ Threshold must be a positive number.", ephemeral=True
            )
            return

        def _insert():
            with get_db() as conn:
                cursor = conn.execute(
                    INSERT_ROUTE,
                    (
                        origin, destination,
                        depart_dt.isoformat(),
                        return_dt.isoformat() if return_dt else None,
                        max_stops, passengers, cabin.upper(), threshold,
                    ),
                )
                return cursor.lastrowid

        route_id = await asyncio.to_thread(_insert)
        arrow = "⇄" if return_dt else "→"
        msg = (
            f"✅ Added route **#{route_id}**: {origin} {arrow} {destination}, "
            f"depart `{depart_dt}`"
            + (f", return `{return_dt}`" if return_dt else " (one-way)")
            + (f", threshold CAD {threshold:,.2f}" if threshold else "")
            + "."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /tracker poll ──────────────────────────────────────────────────────────

    @tracker.command(name="poll")
    @app_commands.describe(route_id="ID of the route to poll")
    async def tracker_poll(self, interaction: discord.Interaction, route_id: int) -> None:
        """Fetch the current cheapest price for a route."""
        if not tracker_config.SERPAPI_KEY:
            await interaction.response.send_message(
                "❌ `SERPAPI_KEY` is not set in `.env`.", ephemeral=True
            )
            return

        def _fetch():
            with get_db() as conn:
                return conn.execute(SELECT_ROUTE_BY_ID, (route_id,)).fetchone()

        row = await asyncio.to_thread(_fetch)
        if not row:
            await interaction.response.send_message(
                f"❌ Route #{route_id} not found.", ephemeral=True
            )
            return

        route = Route.from_row(row)
        if not route.active:
            await interaction.response.send_message(
                f"⏸️ Route #{route_id} is paused. Use `/tracker resume {route_id}` first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        from tracker import serpapi_client

        result = None
        success = False
        try:
            result = await asyncio.to_thread(serpapi_client.search, route)
            success = True
        except Exception as exc:
            logger.error("Discord poll failed for route #%d: %s", route_id, exc)

        def _save():
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
                return cursor.lastrowid

        snapshot_id = await asyncio.to_thread(_save)

        if result:
            stops_label = f"{result.stops} stop" + ("s" if result.stops != 1 else "")
            embed = discord.Embed(
                title=f"Poll: {route.origin} → {route.destination}",
                color=EMBED_COLOR,
            )
            embed.add_field(name="Price", value=f"CAD {result.price_cad:,.2f}", inline=True)
            embed.add_field(name="Carrier", value=result.carrier, inline=True)
            embed.add_field(name="Stops", value=stops_label, inline=True)
            if route.absolute_threshold_cad:
                diff = result.price_cad - route.absolute_threshold_cad
                label = (
                    f"✅ CAD {abs(diff):,.2f} above threshold"
                    if diff >= 0
                    else f"🚨 CAD {abs(diff):,.2f} below threshold!"
                )
                embed.add_field(name="Threshold", value=label, inline=False)
            embed.set_footer(text=f"snapshot id={snapshot_id}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"❌ Poll failed — no results from Serpapi (snapshot id={snapshot_id}).",
                ephemeral=True,
            )

    # ── /tracker pause ─────────────────────────────────────────────────────────

    @tracker.command(name="pause")
    @app_commands.describe(route_id="ID of the route to pause")
    async def tracker_pause(self, interaction: discord.Interaction, route_id: int) -> None:
        """Pause polling for a route."""
        def _update():
            with get_db() as conn:
                row = conn.execute(SELECT_ROUTE_BY_ID, (route_id,)).fetchone()
                if row and row["active"]:
                    conn.execute(UPDATE_ROUTE_ACTIVE, (0, route_id))
                return row

        row = await asyncio.to_thread(_update)
        if not row:
            await interaction.response.send_message(
                f"❌ Route #{route_id} not found.", ephemeral=True
            )
            return
        if not row["active"]:
            await interaction.response.send_message(
                f"Route #{route_id} is already paused.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"⏸️ Paused route #{route_id} ({row['origin']}→{row['destination']}).",
            ephemeral=True,
        )

    # ── /tracker resume ────────────────────────────────────────────────────────

    @tracker.command(name="resume")
    @app_commands.describe(route_id="ID of the route to resume")
    async def tracker_resume(self, interaction: discord.Interaction, route_id: int) -> None:
        """Resume polling for a paused route."""
        def _update():
            with get_db() as conn:
                row = conn.execute(SELECT_ROUTE_BY_ID, (route_id,)).fetchone()
                if row and not row["active"]:
                    conn.execute(UPDATE_ROUTE_ACTIVE, (1, route_id))
                return row

        row = await asyncio.to_thread(_update)
        if not row:
            await interaction.response.send_message(
                f"❌ Route #{route_id} not found.", ephemeral=True
            )
            return
        if row["active"]:
            await interaction.response.send_message(
                f"Route #{route_id} is already active.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"▶️ Resumed route #{route_id} ({row['origin']}→{row['destination']}).",
            ephemeral=True,
        )

    # ── /tracker remove ────────────────────────────────────────────────────────

    @tracker.command(name="remove")
    @app_commands.describe(route_id="ID of the route to delete")
    async def tracker_remove(self, interaction: discord.Interaction, route_id: int) -> None:
        """Permanently delete a route and all its price history."""
        def _delete():
            with get_db() as conn:
                row = conn.execute(SELECT_ROUTE_BY_ID, (route_id,)).fetchone()
                if row:
                    conn.execute(DELETE_ROUTE, (route_id,))
                return row

        row = await asyncio.to_thread(_delete)
        if not row:
            await interaction.response.send_message(
                f"❌ Route #{route_id} not found.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"🗑️ Removed route #{route_id} ({row['origin']}→{row['destination']}).",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrackerCog(bot))
