"""
chewyBot configuration module.

Loads all secrets and settings from .env via pydantic-settings v2.
Exposes a typed Config object and an EMBED_COLOR constant used by all cogs.

Fail-fast: if any required env var is missing, prints a descriptive error
listing ALL missing vars and calls sys.exit(1) — the bot never starts in a
partial-config state.
"""

import sys
from typing import Optional
from pydantic import field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Consistent embed color used across all cogs (dark green — not default blurple)
EMBED_COLOR: int = 0x2E7D32


class Config(BaseSettings):
    """Typed configuration loaded from environment variables / .env file.

    Required fields (no default) will raise ValidationError on startup if absent.
    Optional fields have sensible defaults that can be overridden in .env.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # ------------------------------------------------------------------ #
    # Required — no default; ValidationError raised if absent             #
    # ------------------------------------------------------------------ #
    DISCORD_TOKEN: str
    GUILD_ID: int
    LOG_CHANNEL_ID: int
    ODDS_API_KEY: str
    ARB_CHANNEL_ID: int
    PARLAY_CHANNEL_ID: int

    # ------------------------------------------------------------------ #
    # Optional — defaults can be overridden in .env                       #
    # ------------------------------------------------------------------ #
    BANKROLL: float = 100.0
    MIN_ARB_PCT: float = 0.5
    MIN_EV_PCT: float = 2.0
    MIN_LEG_SCORE: float = 0.5
    SCAN_INTERVAL_SECONDS: int = 60
    PARLAY_POST_TIME: str = "11:00"
    PARLAY_LEARNING_RATE: float = 0.05
    TTS_INTERRUPTS_MUSIC: bool = False
    TTS_MAX_CHARS: int = 300
    MOCK_MODE: bool = False
    ENABLED_SPORTS: str = "basketball_nba,americanfootball_nfl,icehockey_nhl"

    def get_enabled_sports_list(self) -> list[str]:
        """Return ENABLED_SPORTS as a list by splitting on commas."""
        return self.ENABLED_SPORTS.split(",")


# ------------------------------------------------------------------ #
# Module-level instantiation — fail fast on any missing/invalid var   #
# ------------------------------------------------------------------ #
try:
    config = Config()
except ValidationError as e:
    missing = [err["loc"][0] for err in e.errors() if err["type"] == "missing"]
    invalid = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors() if err["type"] != "missing"]
    lines = []
    if missing:
        lines.append(f"Missing required env vars: {', '.join(str(m) for m in missing)}")
    if invalid:
        lines.extend(invalid)
    print("chewyBot configuration error:\n" + "\n".join(f"  - {l}" for l in lines))
    sys.exit(1)
