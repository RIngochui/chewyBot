from __future__ import annotations
import discord
from config import EMBED_COLOR
from models.signals import ArbSignal, EVSignal
from models.parlay import Parlay


def build_arb_embed(signal: ArbSignal) -> discord.Embed:
    """Build a Discord embed for an arbitrage alert.

    ARB-20: title contains 'Possible Arbitrage'
    ARB-22: footer uses 'possible' / 'estimated' language (no profit claims)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    embed = discord.Embed(
        title="⚡ Possible Arbitrage — chewyBot",
        color=EMBED_COLOR,
        timestamp=signal.detected_at,
    )
    embed.add_field(name="Sport", value=signal.sport, inline=True)
    embed.add_field(name="Event", value=signal.event_name, inline=True)
    embed.add_field(name="Market", value=signal.market_type, inline=True)
    embed.add_field(
        name="Side A",
        value=(
            f"{signal.selection_a} @ {signal.book_a} — "
            f"{signal.odds_a:.3f} (stake: ${signal.stake_side_a:.2f})"
        ),
        inline=False,
    )
    embed.add_field(
        name="Side B",
        value=(
            f"{signal.selection_b} @ {signal.book_b} — "
            f"{signal.odds_b:.3f} (stake: ${signal.stake_side_b:.2f})"
        ),
        inline=False,
    )
    embed.add_field(name="Arb %", value=f"{signal.arb_pct:.2f}%", inline=True)
    embed.add_field(
        name="Est. Profit", value=f"${signal.estimated_profit:.2f}", inline=True
    )
    embed.set_footer(
        text="Not financial advice. Results are estimated and may not be realised."
    )
    return embed


def build_ev_embed(signal: EVSignal) -> discord.Embed:
    """Build a Discord embed for a +EV opportunity alert.

    ARB-21: title contains '+EV Opportunity'
    ARB-22: footer uses 'possible' / 'estimated' language (no profit claims)
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 3 full implementation.
    """
    embed = discord.Embed(
        title="📈 +EV Opportunity — chewyBot",
        color=EMBED_COLOR,
        timestamp=signal.detected_at,
    )
    embed.add_field(name="Sport", value=signal.sport, inline=True)
    embed.add_field(name="Event", value=signal.event_name, inline=True)
    embed.add_field(name="Market", value=signal.market_type, inline=True)
    embed.add_field(name="Outcome", value=signal.selection_name, inline=True)
    embed.add_field(name="Book", value=signal.book_name, inline=True)
    embed.add_field(
        name="Offered Odds", value=f"{signal.decimal_odds:.3f} (decimal)", inline=True
    )
    embed.add_field(
        name="Fair Probability",
        value=f"{signal.fair_probability * 100:.1f}%",
        inline=True,
    )
    embed.add_field(name="EV %", value=f"{signal.ev_pct:.2f}%", inline=True)
    embed.set_footer(
        text="Not financial advice. Results are estimated and may not be realised."
    )
    return embed


def build_parlay_embed(parlay: Parlay, post_date: str) -> discord.Embed:
    """Build a Discord embed for a daily NBA parlay post.

    PAR-10: title "chewyBot's NBA Parlay [date]"
    Fields: each leg (team, market type, line, American odds), combined odds, confidence score
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 4 full implementation.
    """
    raise NotImplementedError("build_parlay_embed() — implement in Phase 4")
