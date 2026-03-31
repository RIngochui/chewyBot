from __future__ import annotations
import discord
from config import EMBED_COLOR
from models.signals import ArbSignal, EVSignal
from models.parlay import Parlay


def build_arb_embed(signal: ArbSignal) -> discord.Embed:
    """Build a Discord embed for an arbitrage alert.

    ARB-20: title "Lightning Bolt Possible Arbitrage chewyBot"
    Fields: sport, event, market, both sides, arb%, stake, profit
    Footer: disclaimer using "possible" / "estimated" language (ARB-22)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    raise NotImplementedError("build_arb_embed() — implement in Phase 3")


def build_ev_embed(signal: EVSignal) -> discord.Embed:
    """Build a Discord embed for a +EV opportunity alert.

    ARB-21: title "+EV Opportunity chewyBot"
    Fields: sport, event, market, book, odds, fair probability, EV%
    Footer: disclaimer using "possible" / "estimated" language (ARB-22)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    raise NotImplementedError("build_ev_embed() — implement in Phase 3")


def build_parlay_embed(parlay: Parlay, post_date: str) -> discord.Embed:
    """Build a Discord embed for a daily NBA parlay post.

    PAR-10: title "chewyBot's NBA Parlay [date]"
    Fields: each leg (team, market type, line, American odds), combined odds, confidence score
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 4 full implementation.
    """
    raise NotImplementedError("build_parlay_embed() — implement in Phase 4")
