"""
SkyShield ME — Application Configuration.

Centralizes all environment-driven configuration with strict
validation via Pydantic Settings. No global mutable state.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ─── Constants ───────────────────────────────────────────────────
MAX_DRONE_ALTITUDE_FT: Final[int] = 5000
MAX_DRONE_SPEED_KTS: Final[int] = 100
SIGHTING_LIVE_WINDOW_MINUTES: Final[int] = 15
ADSB_POLL_INTERVAL_SECONDS: Final[int] = 30
TELEGRAM_POLL_INTERVAL_SECONDS: Final[int] = 60


class Settings(BaseSettings):
    """Immutable application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://skyshield:skyshield_secret@localhost:5432/skyshield_me",
        description="Async PostgreSQL connection string",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        """Ensure the DB URL uses the asyncpg driver.

        Railway provides DATABASE_URL as postgresql://... which needs
        conversion to postgresql+asyncpg:// for SQLAlchemy async.
        """
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            value = value.replace("postgres://", "postgresql+asyncpg://", 1)
        elif value.startswith("postgresql://") and "+asyncpg" not in value:
            value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    # ── Redis / Celery ───────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # ── ADS-B Exchange ───────────────────────────────────────────
    adsb_api_key: str = Field(default="", description="ADS-B Exchange API key")
    adsb_api_url: str = Field(
        default="https://adsbexchange.com/api/aircraft/json",
        description="ADS-B Exchange endpoint",
    )

    # ── Telegram ─────────────────────────────────────────────────
    telegram_api_id: str = Field(default="", description="Telegram API ID")
    telegram_api_hash: str = Field(default="", description="Telegram API hash")
    telegram_session_name: str = Field(default="skyshield_session")

    # ── Application ──────────────────────────────────────────────
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _validate_cors(cls, value: str) -> str:
        if not isinstance(value, str):
            error_msg: str = "CORS_ORIGINS must be a comma-separated string"
            raise ValueError(error_msg)
        return value

    def get_cors_list(self) -> list[str]:
        """Return CORS origins as a list of strings.

        Includes Railway's auto-generated *.up.railway.app domains.
        """
        origins: list[str] = [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]
        # Railway auto-generates https://*.up.railway.app domains
        if not any("railway.app" in o for o in origins):
            origins.append("https://*.up.railway.app")
        return origins

    def is_adsb_configured(self) -> bool:
        """Check if ADS-B Exchange credentials are present."""
        return bool(self.adsb_api_key)

    def is_telegram_configured(self) -> bool:
        """Check if Telegram credentials are present."""
        return bool(self.telegram_api_id and self.telegram_api_hash)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton settings loader."""
    return Settings()
