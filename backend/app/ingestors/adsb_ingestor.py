"""
SkyShield ME — ADS-B Exchange Ingestor.

Polls ADS-B Exchange for aircraft telemetry and filters for
drone-profile contacts (alt < 5000ft, speed < 100kts).
Falls back to a synthetic data generator when no API key is configured.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Final
from uuid import uuid4

import httpx
from celery import shared_task

from app.core import (
    MAX_DRONE_ALTITUDE_FT,
    MAX_DRONE_SPEED_KTS,
    get_settings,
)
from app.schemas import SightingCreate

logger: logging.Logger = logging.getLogger(__name__)

# ─── Middle East bounding box for mock generation ────────────────
ME_LAT_MIN: Final[float] = 24.0
ME_LAT_MAX: Final[float] = 38.0
ME_LON_MIN: Final[float] = 40.0
ME_LON_MAX: Final[float] = 56.0

# ─── Known cities for realistic mock distribution ────────────────
MOCK_HOTSPOTS: Final[list[tuple[float, float, str]]] = [
    (36.19, 44.00, "Erbil"),
    (33.31, 44.37, "Baghdad"),
    (25.28, 51.53, "Al Udeid"),
    (24.45, 54.65, "Al Dhafra"),
    (32.41, 53.69, "Isfahan"),
    (29.26, 47.97, "Kuwait City"),
    (26.27, 50.21, "Bahrain"),
    (36.21, 37.16, "Aleppo"),
]


def _generate_mock_sightings(count: int = 5) -> list[SightingCreate]:
    """
    Produce synthetic ADS-B-like sightings for development.

    Clusters contacts around known ME airfields and urban centers
    with drone-plausible altitude and speed profiles.
    """
    sightings: list[SightingCreate] = []

    for _ in range(count):
        base_lat: float
        base_lon: float
        base_name: str
        base_lat, base_lon, base_name = random.choice(MOCK_HOTSPOTS)

        lat: float = base_lat + random.uniform(-0.3, 0.3)
        lon: float = base_lon + random.uniform(-0.3, 0.3)
        alt: float = random.uniform(50.0, float(MAX_DRONE_ALTITUDE_FT))
        speed: float = random.uniform(5.0, float(MAX_DRONE_SPEED_KTS))
        heading: float = random.uniform(0.0, 360.0)
        confidence: int = random.randint(40, 95)

        # Generate plausible ICAO hex and callsign
        icao_hex: str = f"{random.randint(0x700000, 0x7FFFFF):06X}"
        callsign: str = f"UNK{random.randint(1000, 9999)}"

        sighting = SightingCreate(
            lat=round(lat, 6),
            lon=round(lon, 6),
            altitude=round(alt, 1),
            speed_kts=round(speed, 1),
            heading=round(heading, 1),
            source="ADSB",
            confidence_score=confidence,
            callsign=callsign,
            icao_hex=icao_hex,
            metadata_json={
                "origin": "mock_generator",
                "hotspot": base_name,
            },
        )
        sightings.append(sighting)

    return sightings


def _filter_drone_profile(aircraft: dict[str, object]) -> bool:
    """
    Determine if an aircraft record matches drone flight characteristics.

    Returns True if altitude < 5000ft AND speed < 100kts.
    """
    alt_value: object = aircraft.get("alt_baro", aircraft.get("altitude", None))
    speed_value: object = aircraft.get("gs", aircraft.get("speed", None))

    if alt_value is None or speed_value is None:
        return False

    try:
        altitude: float = float(str(alt_value))
        speed: float = float(str(speed_value))
    except (ValueError, TypeError):
        return False

    is_low_altitude: bool = altitude < MAX_DRONE_ALTITUDE_FT
    is_slow_speed: bool = speed < MAX_DRONE_SPEED_KTS

    return is_low_altitude and is_slow_speed


async def _fetch_live_adsb() -> list[SightingCreate]:
    """
    Query ADS-B Exchange API for live aircraft in the ME bounding box.

    Falls back to mock data if API key is not configured.
    """
    settings = get_settings()

    if not settings.is_adsb_configured():
        logger.warning("ADS-B API key not configured — using mock data")
        return _generate_mock_sightings(count=random.randint(2, 8))

    sightings: list[SightingCreate] = []
    url: str = settings.adsb_api_url

    headers: dict[str, str] = {
        "api-auth": settings.adsb_api_key,
        "Accept": "application/json",
    }

    params: dict[str, str] = {
        "lamin": str(ME_LAT_MIN),
        "lamax": str(ME_LAT_MAX),
        "lomin": str(ME_LON_MIN),
        "lomax": str(ME_LON_MAX),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response: httpx.Response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data: dict[str, object] = response.json()

        aircraft_list: list[dict[str, object]] = data.get("ac", data.get("aircraft", []))

        for ac in aircraft_list:
            if not _filter_drone_profile(ac):
                continue

            lat_raw: object = ac.get("lat")
            lon_raw: object = ac.get("lon")

            if lat_raw is None or lon_raw is None:
                continue

            sighting = SightingCreate(
                lat=float(str(lat_raw)),
                lon=float(str(lon_raw)),
                altitude=float(str(ac.get("alt_baro", 0))),
                speed_kts=float(str(ac.get("gs", 0))),
                heading=float(str(ac.get("track", 0))),
                source="ADSB",
                confidence_score=85,
                callsign=str(ac.get("flight", "")).strip() or None,
                icao_hex=str(ac.get("hex", "")).strip() or None,
                metadata_json={"raw_frame": str(ac)},
            )
            sightings.append(sighting)

    except httpx.HTTPStatusError as exc:
        logger.error("ADS-B API HTTP error: %s", exc.response.status_code)
    except httpx.RequestError as exc:
        logger.error("ADS-B API request error: %s", exc)
    except (KeyError, ValueError) as exc:
        logger.error("ADS-B response parse error: %s", exc)

    return sightings


@shared_task(name="app.ingestors.adsb_ingestor.poll_adsb", bind=True, max_retries=3)
def poll_adsb(self) -> dict[str, int]:  # noqa: ANN001 — Celery self
    """
    Celery task: poll ADS-B Exchange and persist filtered contacts.

    Bridges sync Celery with the async DB layer via asyncio.run().
    """
    try:
        sightings: list[SightingCreate] = asyncio.get_event_loop().run_until_complete(
            _fetch_live_adsb(),
        )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        sightings = loop.run_until_complete(_fetch_live_adsb())
        loop.close()

    # Persist via synchronous bridge (Celery tasks are sync)
    count: int = _persist_sightings_sync(sightings)
    logger.info("ADS-B poll complete: %d contacts ingested", count)
    return {"ingested": count}


def _persist_sightings_sync(sightings: list[SightingCreate]) -> int:
    """
    Synchronous wrapper to persist sightings from Celery context.

    Uses a dedicated sync engine for Celery worker compatibility.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SyncSession

    from app.core import get_settings
    from app.db.models import Sighting, SightingSource

    settings = get_settings()
    sync_url: str = settings.get_sync_database_url()

    sync_engine = create_engine(sync_url, pool_pre_ping=True)
    persisted: int = 0

    try:
        with SyncSession(sync_engine) as session:
            for payload in sightings:
                sighting = Sighting(
                    id=str(uuid4()),
                    lat=payload.lat,
                    lon=payload.lon,
                    altitude=payload.altitude,
                    speed_kts=payload.speed_kts,
                    heading=payload.heading,
                    source=SightingSource(payload.source),
                    confidence_score=payload.confidence_score,
                    callsign=payload.callsign,
                    icao_hex=payload.icao_hex,
                    metadata_json=payload.metadata_json,
                )
                session.add(sighting)
                persisted += 1
            session.commit()
    except Exception as exc:
        logger.error("Sighting persistence error: %s", exc)

    return persisted
