"""
SkyShield ME — Sighting Service.

Encapsulates all database operations for sighting records.
Functions are small, focused, and use explicit types throughout.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import SIGHTING_LIVE_WINDOW_MINUTES
from app.db.models import Sighting, SightingSource
from app.schemas import HeatmapPoint, SightingCreate

logger: logging.Logger = logging.getLogger(__name__)


async def create_sighting(
    session: AsyncSession,
    payload: SightingCreate,
) -> Sighting:
    """
    Persist a new sighting record with PostGIS point geometry.

    Returns the created Sighting ORM instance.
    """
    sighting = Sighting(
        lat=payload.lat,
        lon=payload.lon,
        altitude=payload.altitude,
        speed_kts=payload.speed_kts,
        heading=payload.heading,
        source=SightingSource(payload.source),
        confidence_score=payload.confidence_score,
        callsign=payload.callsign,
        icao_hex=payload.icao_hex,
        raw_text=payload.raw_text,
        metadata_json=payload.metadata_json,
        geom=func.ST_SetSRID(func.ST_MakePoint(payload.lon, payload.lat), 4326),
    )
    session.add(sighting)
    await session.commit()
    await session.refresh(sighting)
    logger.info("Created sighting id=%s src=%s", sighting.id[:8], sighting.source.value)
    return sighting


async def get_live_sightings(
    session: AsyncSession,
    source_filter: Optional[str] = None,
    limit: int = 500,
) -> list[Sighting]:
    """
    Return sightings within the live window (last N minutes).

    Optionally filtered by source type.
    """
    cutoff: datetime = datetime.now(tz=timezone.utc) - timedelta(
        minutes=SIGHTING_LIVE_WINDOW_MINUTES,
    )

    stmt = (
        select(Sighting)
        .where(Sighting.timestamp >= cutoff)
        .order_by(Sighting.timestamp.desc())
        .limit(limit)
    )

    if source_filter is not None:
        stmt = stmt.where(Sighting.source == SightingSource(source_filter))

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_heatmap_data(
    session: AsyncSession,
    hours: int = 24,
    grid_precision: int = 2,
) -> list[HeatmapPoint]:
    """
    Aggregate sightings into heatmap grid cells.

    Groups by rounded lat/lon at the specified decimal precision
    and returns intensity-normalized points.
    """
    cutoff: datetime = datetime.now(tz=timezone.utc) - timedelta(hours=hours)

    stmt = (
        select(
            func.round(Sighting.lat, grid_precision).label("grid_lat"),
            func.round(Sighting.lon, grid_precision).label("grid_lon"),
            func.count().label("cnt"),
        )
        .where(Sighting.timestamp >= cutoff)
        .group_by(
            func.round(Sighting.lat, grid_precision),
            func.round(Sighting.lon, grid_precision),
        )
    )

    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    max_count: int = max(row.cnt for row in rows)
    points: list[HeatmapPoint] = []

    for row in rows:
        intensity: float = row.cnt / max_count if max_count > 0 else 0.0
        point = HeatmapPoint(
            lat=float(row.grid_lat),
            lon=float(row.grid_lon),
            intensity=intensity,
            count=row.cnt,
        )
        points.append(point)

    return points


async def get_total_sightings_count(
    session: AsyncSession,
    hours: int = 24,
) -> int:
    """Return total sighting count within the time window."""
    cutoff: datetime = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    stmt = select(func.count()).select_from(Sighting).where(Sighting.timestamp >= cutoff)
    result = await session.execute(stmt)
    count: int = result.scalar_one_or_none() or 0
    return count
