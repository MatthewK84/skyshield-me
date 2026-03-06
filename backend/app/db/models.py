"""
SkyShield ME — Database Models.

Defines the Sighting ORM model with PostGIS point geometry,
source enum, and JSON metadata for raw intel storage.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SightingSource(str, enum.Enum):
    """Enumeration of data provenance sources."""

    ADSB = "ADSB"
    SOCIAL_INFERENCE = "SOCIAL_INFERENCE"


class Sighting(Base):
    """
    Core detection record.

    Each row represents a single observed or inferred UAS/aircraft contact
    fused from ADS-B telemetry or social media signal extraction.
    """

    __tablename__ = "sightings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True,
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_kts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heading: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    source: Mapped[SightingSource] = mapped_column(
        Enum(SightingSource, name="sighting_source_enum"),
        nullable=False,
        index=True,
    )
    confidence_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="0-100 confidence rating",
    )

    callsign: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    icao_hex: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    # PostGIS geometry column for spatial queries
    geom = Column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=True,
        comment="WGS84 point for spatial indexing",
    )

    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Raw payload: tweet text, telegram message, ADS-B frame",
    )

    raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Original social media text triggering the sighting",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_sightings_timestamp_source", "timestamp", "source"),
        Index("idx_sightings_geom", "geom", postgresql_using="gist"),
    )

    def __repr__(self) -> str:
        return (
            f"<Sighting id={self.id[:8]}... "
            f"src={self.source.value} "
            f"conf={self.confidence_score} "
            f"({self.lat:.4f}, {self.lon:.4f})>"
        )
