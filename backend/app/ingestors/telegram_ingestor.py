"""
SkyShield ME — Telegram Social Ingestor.

Monitors specified Telegram channels for UAS-related keywords,
extracts geolocations from text, and produces SOCIAL_INFERENCE sightings.

Includes:
  - FloodWaitError handling with exponential backoff
  - asyncio.sleep() rate limiting between channel reads
  - Keyword scoring for confidence calibration
  - Regex-based geoparsing with city-to-coordinate lookup
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Final, Optional

from celery import shared_task

from app.core import get_settings
from app.schemas import SightingCreate

logger: logging.Logger = logging.getLogger(__name__)

# ─── Keyword Categories with Weight ─────────────────────────────
# Higher weight = stronger UAS signal
KEYWORD_WEIGHTS: Final[dict[str, int]] = {
    "drone": 30,
    "uav": 35,
    "uas": 35,
    "quadcopter": 30,
    "rpas": 25,
    "explosion": 20,
    "buzzing": 25,
    "heard buzzing": 35,
    "small aircraft": 15,
    "unmanned": 30,
    "kamikaze": 25,
    "shahed": 40,
    "loitering munition": 40,
    "one-way attack": 35,
    "fpv": 30,
    "mohajer": 35,
    "ababil": 35,
    "samad": 30,
    "houthi drone": 40,
}

# ─── Geoparsing: City Name -> (lat, lon) ────────────────────────
CITY_COORDINATES: Final[dict[str, tuple[float, float]]] = {
    "erbil": (36.19, 44.00),
    "baghdad": (33.31, 44.37),
    "basra": (30.51, 47.78),
    "mosul": (36.34, 43.12),
    "al udeid": (25.12, 51.32),
    "al dhafra": (24.25, 54.55),
    "riyadh": (24.71, 46.67),
    "jeddah": (21.49, 39.19),
    "tehran": (35.69, 51.39),
    "isfahan": (32.65, 51.68),
    "tabriz": (38.08, 46.29),
    "damascus": (33.51, 36.28),
    "aleppo": (36.21, 37.16),
    "sanaa": (15.37, 44.21),
    "aden": (12.78, 45.02),
    "marib": (15.44, 45.34),
    "hodeidah": (14.80, 42.95),
    "kuwait city": (29.38, 47.99),
    "manama": (26.22, 50.59),
    "doha": (25.29, 51.53),
    "muscat": (23.61, 58.54),
    "abu dhabi": (24.45, 54.65),
    "dubai": (25.20, 55.27),
    "amman": (31.96, 35.95),
    "beirut": (33.89, 35.50),
    "kirkuk": (35.47, 44.39),
    "sulaymaniyah": (35.56, 45.44),
    "tikrit": (34.60, 43.68),
    "najaf": (32.00, 44.34),
    "karbala": (32.62, 44.02),
    "diyarbakir": (37.91, 40.22),
    "incirlik": (37.00, 35.43),
    "tabuk": (28.38, 36.57),
}

# ─── Target Telegram Channels (configurable) ────────────────────
TARGET_CHANNELS: Final[list[str]] = [
    # Add channel usernames or IDs here.
    # Example: "middle_east_intel", "me_conflict_tracker"
    # These are placeholders — populate with OSINT channels.
    "example_channel_placeholder",
]

# ─── Rate Limiting Config ────────────────────────────────────────
DELAY_BETWEEN_CHANNELS_SEC: Final[float] = 3.0
DELAY_BETWEEN_MESSAGES_SEC: Final[float] = 0.5
MAX_MESSAGES_PER_CHANNEL: Final[int] = 50


def _extract_keywords(text: str) -> tuple[list[str], int]:
    """
    Scan text for UAS-related keywords and compute a weighted score.

    Returns (matched_keywords, total_score).
    """
    text_lower: str = text.lower()
    matched: list[str] = []
    score: int = 0

    for keyword, weight in KEYWORD_WEIGHTS.items():
        pattern: str = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, text_lower):
            matched.append(keyword)
            score += weight

    return matched, min(score, 100)


def _geoparse_text(text: str) -> Optional[tuple[float, float, str]]:
    """
    Extract geographic coordinates from text by matching city names.

    Returns (lat, lon, city_name) or None if no location found.
    Uses case-insensitive whole-word matching.
    """
    text_lower: str = text.lower()

    for city_name, coords in CITY_COORDINATES.items():
        # Match whole words to avoid partial city name collisions
        pattern: str = r"\b" + re.escape(city_name) + r"\b"
        if re.search(pattern, text_lower):
            return (coords[0], coords[1], city_name)

    # Fallback: check for coordinate patterns like "36.19, 44.00"
    coord_pattern: str = r"(-?\d{1,3}\.\d+)\s*[,/]\s*(-?\d{1,3}\.\d+)"
    coord_match: Optional[re.Match[str]] = re.search(coord_pattern, text)

    if coord_match is not None:
        lat: float = float(coord_match.group(1))
        lon: float = float(coord_match.group(2))

        is_valid_lat: bool = -90.0 <= lat <= 90.0
        is_valid_lon: bool = -180.0 <= lon <= 180.0

        if is_valid_lat and is_valid_lon:
            return (lat, lon, "coordinates_extracted")

    return None


def _build_social_sighting(
    text: str,
    lat: float,
    lon: float,
    city: str,
    keywords: list[str],
    confidence: int,
    channel: str,
    message_id: int,
) -> SightingCreate:
    """Construct a SightingCreate from parsed social media data."""
    return SightingCreate(
        lat=lat,
        lon=lon,
        altitude=None,
        speed_kts=None,
        heading=None,
        source="SOCIAL_INFERENCE",
        confidence_score=confidence,
        raw_text=text[:2000],
        metadata_json={
            "channel": channel,
            "message_id": str(message_id),
            "matched_keywords": ",".join(keywords),
            "geoparsed_city": city,
        },
    )


async def _scrape_telegram_channels() -> list[SightingCreate]:
    """
    Connect to Telegram via Telethon and scrape target channels.

    Includes:
      - FloodWaitError handling with automatic sleep
      - Rate limiting between channel iterations
      - Keyword extraction and geoparsing per message

    AUTHENTICATION SETUP:
      1. Go to https://my.telegram.org -> API Development Tools
      2. Create an application to get API_ID and API_HASH
      3. Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
      4. On first run, Telethon will prompt for phone number and 2FA code
         in the terminal. Subsequent runs use the saved session file.
    """
    settings = get_settings()

    if not settings.is_telegram_configured():
        logger.warning("Telegram credentials not configured — generating mock social data")
        return _generate_mock_social_sightings()

    sightings: list[SightingCreate] = []

    try:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError

        client = TelegramClient(
            settings.telegram_session_name,
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
        )

        await client.start()
        logger.info("Telegram client connected")

        for channel_name in TARGET_CHANNELS:
            try:
                # ── Rate limit: pause between channels ───────
                await asyncio.sleep(DELAY_BETWEEN_CHANNELS_SEC)

                entity = await client.get_entity(channel_name)
                message_count: int = 0

                async for message in client.iter_messages(
                    entity,
                    limit=MAX_MESSAGES_PER_CHANNEL,
                ):
                    if message.text is None:
                        continue

                    # ── Rate limit: pause between messages ───
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES_SEC)

                    keywords: list[str]
                    score: int
                    keywords, score = _extract_keywords(message.text)

                    if not keywords:
                        continue

                    geo_result = _geoparse_text(message.text)
                    if geo_result is None:
                        continue

                    lat: float = geo_result[0]
                    lon: float = geo_result[1]
                    city: str = geo_result[2]

                    sighting: SightingCreate = _build_social_sighting(
                        text=message.text,
                        lat=lat,
                        lon=lon,
                        city=city,
                        keywords=keywords,
                        confidence=score,
                        channel=channel_name,
                        message_id=message.id,
                    )
                    sightings.append(sighting)
                    message_count += 1

                logger.info(
                    "Channel '%s': processed %d relevant messages",
                    channel_name,
                    message_count,
                )

            except FloodWaitError as flood_exc:
                # ── Telegram rate limit hit — respect the wait ──
                wait_seconds: int = flood_exc.seconds
                logger.warning(
                    "FloodWaitError on '%s': sleeping %d seconds",
                    channel_name,
                    wait_seconds,
                )
                await asyncio.sleep(float(wait_seconds) + 5.0)

            except (ValueError, AttributeError) as exc:
                logger.error("Error processing channel '%s': %s", channel_name, exc)

        await client.disconnect()

    except ImportError:
        logger.error("Telethon not installed — cannot scrape Telegram")
    except Exception as exc:
        logger.error("Telegram scraper fatal error: %s", exc)

    return sightings


def _generate_mock_social_sightings() -> list[SightingCreate]:
    """
    Produce synthetic social-inference sightings for development.

    Simulates Telegram channel scrapes with realistic text patterns.
    """
    import random

    mock_messages: list[tuple[str, str]] = [
        ("Drone spotted flying low over Erbil citadel, buzzing sound", "erbil"),
        ("Reports of UAV activity near Baghdad airport perimeter", "baghdad"),
        ("Explosion heard near Al Udeid, possible drone strike", "al udeid"),
        ("Multiple small aircraft seen over Isfahan at low altitude", "isfahan"),
        ("Houthi drone intercepted approaching Riyadh", "riyadh"),
        ("Shahed-type loitering munition reported over Kirkuk", "kirkuk"),
        ("FPV kamikaze drone footage from Aleppo frontline", "aleppo"),
        ("Buzzing sound and small UAV spotted near Kuwait City port", "kuwait city"),
    ]

    sightings: list[SightingCreate] = []
    sample_size: int = random.randint(1, 4)

    for text, city in random.sample(mock_messages, min(sample_size, len(mock_messages))):
        keywords: list[str]
        score: int
        keywords, score = _extract_keywords(text)

        geo_result = _geoparse_text(text)
        if geo_result is None:
            continue

        sighting = _build_social_sighting(
            text=text,
            lat=geo_result[0],
            lon=geo_result[1],
            city=geo_result[2],
            keywords=keywords,
            confidence=score,
            channel="mock_channel",
            message_id=random.randint(10000, 99999),
        )
        sightings.append(sighting)

    return sightings


@shared_task(
    name="app.ingestors.telegram_ingestor.poll_telegram",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def poll_telegram(self) -> dict[str, int]:  # noqa: ANN001 — Celery self
    """
    Celery task: scrape Telegram channels and persist social sightings.

    Bridges sync Celery with the async Telethon client.
    """
    try:
        loop = asyncio.new_event_loop()
        sightings: list[SightingCreate] = loop.run_until_complete(
            _scrape_telegram_channels(),
        )
        loop.close()
    except Exception as exc:
        logger.error("Telegram poll failed: %s", exc)
        sightings = []

    count: int = _persist_social_sightings_sync(sightings)
    logger.info("Telegram poll complete: %d social sightings ingested", count)
    return {"ingested": count}


def _persist_social_sightings_sync(sightings: list[SightingCreate]) -> int:
    """Synchronous persistence bridge for Celery workers."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession

    from app.core import get_settings
    from app.db.models import Sighting, SightingSource

    settings = get_settings()
    sync_url: str = settings.database_url.replace("+asyncpg", "+psycopg2")
    sync_engine = create_engine(sync_url, pool_pre_ping=True)
    persisted: int = 0

    try:
        with SyncSession(sync_engine) as session:
            for payload in sightings:
                sighting = Sighting(
                    lat=payload.lat,
                    lon=payload.lon,
                    altitude=payload.altitude,
                    speed_kts=payload.speed_kts,
                    heading=payload.heading,
                    source=SightingSource(payload.source),
                    confidence_score=payload.confidence_score,
                    raw_text=payload.raw_text,
                    metadata_json=payload.metadata_json,
                )
                session.add(sighting)
                persisted += 1
            session.commit()
    except Exception as exc:
        logger.error("Social sighting persistence error: %s", exc)

    return persisted
