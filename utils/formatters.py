from __future__ import annotations
import discord
from zoneinfo import ZoneInfo
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
    if signal.game_time is not None:
        et = signal.game_time.astimezone(ZoneInfo("America/New_York"))
        embed.add_field(name="Game Date", value=et.strftime("%-I:%M %p ET, %a %b %-d %Y"), inline=True)
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
    embed.add_field(
        name="How to play this",
        value=(
            f"1. Go to **{signal.book_a}** → bet **${signal.stake_side_a:.2f}** on **{signal.selection_a}**\n"
            f"2. Go to **{signal.book_b}** → bet **${signal.stake_side_b:.2f}** on **{signal.selection_b}**\n"
            f"3. Either way, you pocket ~**${signal.estimated_profit:.2f}**"
        ),
        inline=False,
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
    if signal.game_time is not None:
        et = signal.game_time.astimezone(ZoneInfo("America/New_York"))
        embed.add_field(name="Game Date", value=et.strftime("%-I:%M %p ET, %a %b %-d %Y"), inline=True)
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
    embed.add_field(
        name="How to play this",
        value=(
            f"1. Go to **{signal.book_name}** → bet on **{signal.selection_name}**\n"
            f"2. The market is pricing this at {signal.decimal_odds:.3f} but fair odds suggest {1 / signal.fair_probability:.3f}\n"
            f"3. Long-term edge: **+{signal.ev_pct:.1f}%** per dollar bet"
        ),
        inline=False,
    )
    embed.set_footer(
        text="Not financial advice. Results are estimated and may not be realised."
    )
    return embed


def build_parlay_embed(parlay: Parlay, post_date: str) -> discord.Embed:
    """Build a Discord embed for a daily NBA parlay post.

    PAR-10: title "chewyBot's NBA Parlay — [date]"
    Fields: one field per leg (team, market type, line, American odds),
            combined parlay odds (American format), confidence score 0-100.
    Footer: reaction prompt to help the AI learn.
    Uses EMBED_COLOR = 0x2E7D32 (BOT-05)
    Phase 4 full implementation.
    """
    from utils.odds_math import decimal_to_american

    embed = discord.Embed(
        title=f"chewyBot's NBA Parlay — {post_date}",
        color=EMBED_COLOR,
    )

    # One field per leg
    for i, leg in enumerate(parlay.legs, 1):
        line_str = f" ({leg.line_value:+.1f})" if leg.line_value is not None else ""
        odds_str = f"+{leg.american_odds}" if leg.american_odds > 0 else str(leg.american_odds)
        embed.add_field(
            name=f"Leg {i}: {leg.team}",
            value=f"{leg.market_type.title()}{line_str} — {odds_str}",
            inline=False,
        )

    # Combined parlay odds in American format
    combined_american = decimal_to_american(parlay.combined_odds)
    combined_str = f"+{combined_american}" if combined_american > 0 else str(combined_american)
    embed.add_field(name="Combined Parlay Odds", value=combined_str, inline=True)
    embed.add_field(name="Confidence", value=f"{parlay.confidence_score:.0f}/100", inline=True)

    embed.set_footer(text="Results will be checked automatically before tomorrow's parlay.")

    return embed


def build_parlay_result_embed(result: dict) -> discord.Embed:
    """Build a Discord embed showing yesterday's parlay outcome.

    result dict keys: parlay_id (int), game_date (str YYYY-MM-DD),
    outcome (str: 'hit'|'miss'|'pending'),
    legs (list of dicts: team, outcome, leg_type)
    """
    _outcome_emoji = {"hit": "✅", "miss": "❌", "pending": "⏳"}
    overall_emoji = _outcome_emoji.get(result["outcome"], "?")
    overall_label = result["outcome"].upper()

    embed = discord.Embed(
        title=f"Yesterday's Parlay — {result['game_date']}",
        description=f"Overall: {overall_emoji} **{overall_label}**",
        color=EMBED_COLOR,
    )

    for leg in result.get("legs", []):
        leg_emoji = _outcome_emoji.get(leg["outcome"], "?")
        embed.add_field(
            name=f"{leg_emoji} {leg['team']}",
            value=leg["leg_type"].replace("_", " ").title(),
            inline=True,
        )

    embed.set_footer(text="Outcomes resolved automatically from game results.")
    return embed
