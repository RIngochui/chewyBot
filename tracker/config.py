"""
Tracker configuration.

Loads tracker-specific settings from .env via pydantic-settings v2.
Uses extra='ignore' so this module is importable on machines where bot
env vars (DISCORD_TOKEN, etc.) are absent or unset.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackerConfig(BaseSettings):
    """Typed settings for the flight price tracker.

    Only tracker-specific vars are declared here. Bot vars are invisible to
    this class thanks to extra='ignore'.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    TRACKER_DB_PATH: str = "data/tracker.db"
    TRACKER_TIMEZONE: str = "America/Toronto"
    SERPAPI_KEY: str  # required — get a free key at serpapi.com
    TRACKER_POLL_INTERVAL_HOURS: float = 4.0  # how often the daemon polls all active routes


config = TrackerConfig()
