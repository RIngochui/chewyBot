"""
Sports arbitrage and +EV scanner cog for chewyBot.

Uses adapter pattern (adapters/odds_api.py) to fetch odds from The Odds API.
MOCK_MODE=true loads from mock/odds_api_sample.json instead of live API.
Scans are triggered manually via /scan — no auto-polling loop.
Slash commands: /ping, /scan, /latest_arbs, /latest_ev, /set_bankroll,
                /set_min_arb, /set_min_ev, /toggle_sport, /status

References: ARB-12 through ARB-19
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from adapters.odds_api import OddsApiAdapter
from config import config, EMBED_COLOR
from database.db import get_db
from database.queries import (
    INSERT_ARB_SIGNAL,
    INSERT_EV_SIGNAL,
    SELECT_LATEST_ARB_SIGNALS,
    SELECT_LATEST_EV_SIGNALS,
    GET_BOT_CONFIG,
    UPDATE_BOT_CONFIG,
)
from models.signals import ArbSignal, EVSignal
from services.arb_detector import detect_arb, detect_ev
from services.odds_normalizer import normalize
from utils.formatters import build_arb_embed, build_ev_embed

logger = logging.getLogger(__name__)


class ArbCog(commands.Cog, name="Arbitrage"):
    """Arbitrage and +EV scanner cog — wires OddsApiAdapter into Discord.

    Scans run on demand via /scan. In-memory dedup prevents re-alerting the
    same market unless arb_pct improves by >0.2% (ARB-09).
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.adapter = OddsApiAdapter(
            api_key=config.ODDS_API_KEY,
            mock_mode=config.MOCK_MODE,
        )
        # Runtime-mutable config (mirrors env defaults; updated by slash commands)
        self._bankroll: float = config.BANKROLL
        self._min_arb_pct: float = config.MIN_ARB_PCT
        self._min_ev_pct: float = config.MIN_EV_PCT
        self._enabled_sports: list[str] = config.get_enabled_sports_list()
        # In-memory dedup: market_key -> last alerted arb_pct or ev_pct (ARB-09)
        self._seen: dict[str, float] = {}
        self._last_scan_at: Optional[datetime] = None

    async def cog_unload(self) -> None:
        """Close the adapter on unload."""
        await self.adapter.close()

    # ------------------------------------------------------------------ #
    # Core scan logic                                                      #
    # ------------------------------------------------------------------ #

    async def _run_scan(self) -> tuple[list[ArbSignal], list[EVSignal]]:
        """Fetch odds for all enabled sports, detect arb/EV, persist, and post embeds.

        Returns:
            Tuple of (arb_signals, ev_signals) found in this scan.
        """
        all_normalized = []
        for sport_key in self._enabled_sports:
            raw_events = await self.adapter.get_odds(
                sport_key=sport_key,
                regions=["us"],
                markets=["h2h", "spreads", "totals"],
            )
            for ev in raw_events:
                records = await normalize(
                    ev,
                    sport_key,
                    ev.get("sport_title", sport_key),
                    supported_books=OddsApiAdapter.SUPPORTED_BOOKS,
                )
                all_normalized.extend(records)

        arb_signals = await detect_arb(all_normalized, self._min_arb_pct, self._bankroll)
        ev_signals = await detect_ev(all_normalized, self._min_ev_pct) if config.ENABLE_EV_SCAN else []

        self._last_scan_at = datetime.now(tz=timezone.utc)

        # Persist ALL signals to DB (regardless of dedup)
        async with get_db() as db:
            for sig in arb_signals:
                await db.execute(INSERT_ARB_SIGNAL, (
                    sig.market_key, sig.event_name, sig.sport, sig.market_type,
                    sig.arb_pct, sig.stake_side_a, sig.stake_side_b, sig.estimated_profit,
                    sig.book_a, sig.book_b, sig.odds_a, sig.odds_b,
                    sig.selection_a, sig.selection_b, sig.detected_at.isoformat(), 0,
                ))
            for sig in ev_signals:
                await db.execute(INSERT_EV_SIGNAL, (
                    sig.market_key, sig.event_name, sig.sport, sig.market_type,
                    sig.selection_name, sig.book_name, sig.decimal_odds,
                    sig.fair_probability, sig.ev_pct, sig.detected_at.isoformat(), 0,
                ))

        # Post to Discord only for signals above dedup threshold (ARB-09)
        channel = self.bot.get_channel(config.ARB_CHANNEL_ID)
        if channel:
            for sig in arb_signals:
                last = self._seen.get(sig.market_key)
                if last is None or (sig.arb_pct - last) > 0.2:
                    await channel.send(embed=build_arb_embed(sig))
                    self._seen[sig.market_key] = sig.arb_pct
            for sig in ev_signals:
                key = f"ev_{sig.market_key}_{sig.book_name}"
                last = self._seen.get(key)
                if last is None or (sig.ev_pct - last) > 0.2:
                    await channel.send(embed=build_ev_embed(sig))
                    self._seen[key] = sig.ev_pct

        return arb_signals, ev_signals

    # ------------------------------------------------------------------ #
    # Slash commands — all guild-scoped                                   #
    # ------------------------------------------------------------------ #

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction) -> None:
        """Report Discord WebSocket latency in milliseconds (ARB-13)."""
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"Pong! Latency: {latency_ms}ms", ephemeral=True
        )

    @app_commands.command(name="scan_arbs", description="Trigger a manual odds scan")
    async def scan(self, interaction: discord.Interaction) -> None:
        """Run an immediate scan and post results to ARB_CHANNEL_ID (ARB-14)."""
        await interaction.response.defer(ephemeral=True)
        try:
            arbs, evs = await self._run_scan()
            await interaction.followup.send(
                f"Scan complete. Found {len(arbs)} arb(s) and {len(evs)} +EV opportunity(ies).",
                ephemeral=True,
            )
        except Exception as exc:
            logger.exception("Manual scan failed")
            await interaction.followup.send(f"Scan failed: {exc}", ephemeral=True)

    @app_commands.command(name="latest_arbs", description="Show last 5 arbitrage alerts")
    async def latest_arbs(self, interaction: discord.Interaction) -> None:
        """Retrieve and display the last 5 arb signals from the database (ARB-15)."""
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            cursor = await db.execute(SELECT_LATEST_ARB_SIGNALS, (5,))
            rows = await cursor.fetchall()
        if not rows:
            await interaction.followup.send("No arb signals recorded yet.", ephemeral=True)
            return
        for row in rows:
            sig = ArbSignal(
                market_key=row["market_key"],
                event_name=row["event_name"],
                sport=row["sport"],
                market_type=row["market_type"],
                arb_pct=row["arb_pct"],
                stake_side_a=row["stake_side_a"],
                stake_side_b=row["stake_side_b"],
                estimated_profit=row["estimated_profit"],
                book_a=row["book_a"],
                book_b=row["book_b"],
                odds_a=row["odds_a"],
                odds_b=row["odds_b"],
                selection_a=row["selection_a"],
                selection_b=row["selection_b"],
                detected_at=datetime.fromisoformat(row["detected_at"]),
            )
            await interaction.followup.send(embed=build_arb_embed(sig), ephemeral=True)

    @app_commands.command(name="latest_ev", description="Show last 5 +EV opportunities")
    async def latest_ev(self, interaction: discord.Interaction) -> None:
        """Retrieve and display the last 5 EV signals from the database (ARB-16)."""
        await interaction.response.defer(ephemeral=True)
        async with get_db() as db:
            cursor = await db.execute(SELECT_LATEST_EV_SIGNALS, (5,))
            rows = await cursor.fetchall()
        if not rows:
            await interaction.followup.send("No +EV signals recorded yet.", ephemeral=True)
            return
        for row in rows:
            sig = EVSignal(
                market_key=row["market_key"],
                event_name=row["event_name"],
                sport=row["sport"],
                market_type=row["market_type"],
                selection_name=row["selection_name"],
                book_name=row["book_name"],
                decimal_odds=row["decimal_odds"],
                fair_probability=row["fair_probability"],
                ev_pct=row["ev_pct"],
                detected_at=datetime.fromisoformat(row["detected_at"]),
            )
            await interaction.followup.send(embed=build_ev_embed(sig), ephemeral=True)

    @app_commands.command(name="set_bankroll", description="Set scanning bankroll")
    @app_commands.describe(amount="Bankroll amount in dollars (e.g. 500.0)")
    async def set_bankroll(self, interaction: discord.Interaction, amount: float) -> None:
        """Update the bankroll used for stake calculations and persist to DB (ARB-17)."""
        if amount <= 0:
            await interaction.response.send_message("Bankroll must be positive.", ephemeral=True)
            return
        self._bankroll = amount
        async with get_db() as db:
            await db.execute(UPDATE_BOT_CONFIG, ("bankroll", str(amount)))
        await interaction.response.send_message(f"Bankroll set to ${amount:.2f}", ephemeral=True)

    @app_commands.command(name="set_min_arb", description="Set minimum arbitrage percentage threshold")
    @app_commands.describe(pct="Minimum arb percentage (e.g. 0.5 for 0.5%)")
    async def set_min_arb(self, interaction: discord.Interaction, pct: float) -> None:
        """Update the minimum arb percentage filter and persist to DB (ARB-17)."""
        if pct < 0:
            await interaction.response.send_message("Minimum arb percentage must be non-negative.", ephemeral=True)
            return
        self._min_arb_pct = pct
        async with get_db() as db:
            await db.execute(UPDATE_BOT_CONFIG, ("min_arb_pct", str(pct)))
        await interaction.response.send_message(f"Min arb percentage set to {pct:.2f}%", ephemeral=True)

    @app_commands.command(name="set_min_ev", description="Set minimum +EV percentage threshold")
    @app_commands.describe(pct="Minimum EV percentage (e.g. 2.0 for 2.0%)")
    async def set_min_ev(self, interaction: discord.Interaction, pct: float) -> None:
        """Update the minimum EV percentage filter and persist to DB (ARB-17)."""
        if pct < 0:
            await interaction.response.send_message("Minimum EV percentage must be non-negative.", ephemeral=True)
            return
        self._min_ev_pct = pct
        async with get_db() as db:
            await db.execute(UPDATE_BOT_CONFIG, ("min_ev_pct", str(pct)))
        await interaction.response.send_message(f"Min EV percentage set to {pct:.2f}%", ephemeral=True)

    @app_commands.command(name="toggle_sport", description="Enable or disable a sport from scanning")
    @app_commands.describe(sport="Sport key, e.g. basketball_nba")
    async def toggle_sport(self, interaction: discord.Interaction, sport: str) -> None:
        """Toggle a sport key on or off in the active scan list and persist to DB (ARB-18)."""
        if sport in self._enabled_sports:
            self._enabled_sports.remove(sport)
            action = "disabled"
        else:
            self._enabled_sports.append(sport)
            action = "enabled"
        persisted = ",".join(self._enabled_sports)
        async with get_db() as db:
            await db.execute(UPDATE_BOT_CONFIG, ("enabled_sports", persisted))
        await interaction.response.send_message(
            f"Sport `{sport}` {action}. Enabled: {persisted or 'none'}", ephemeral=True
        )

    @app_commands.command(name="status", description="Show scanner status and config")
    async def status(self, interaction: discord.Interaction) -> None:
        """Display current scanner configuration, quota, and running status (ARB-19)."""
        last = (
            self._last_scan_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self._last_scan_at
            else "Never"
        )
        quota = self.adapter.get_quota_remaining()
        embed = discord.Embed(title="chewyBot — Scanner Status", color=EMBED_COLOR)
        embed.add_field(name="Bankroll", value=f"${self._bankroll:.2f}", inline=True)
        embed.add_field(name="Min Arb %", value=f"{self._min_arb_pct:.2f}%", inline=True)
        embed.add_field(name="Min EV %", value=f"{self._min_ev_pct:.2f}%", inline=True)
        embed.add_field(
            name="Enabled Sports",
            value=", ".join(self._enabled_sports) or "None",
            inline=False,
        )
        embed.add_field(name="Last Scan", value=last, inline=True)
        embed.add_field(
            name="API Quota Remaining",
            value=str(quota) if quota is not None else "Unknown (mock mode)",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    """Discord.py cog setup hook. Guild sync is handled centrally in bot.py on_ready."""
    cog = ArbCog(bot)
    await bot.add_cog(cog)
