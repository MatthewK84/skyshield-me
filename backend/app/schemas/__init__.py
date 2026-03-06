"""
SkyShield ME — Pydantic Schemas.

Request and response models for the API layer.
All fields are explicitly typed — no use of `Any`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class SightingBase(BaseModel):
    """Shared fields for sighting creation and response."""

    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude WGS84")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude WGS84")
    altitude: Optional[float] = Field(default=None, ge=0.0, description="Altitude in feet")
    speed_kts: Optional[float] = Field(default=None, ge=0.0, description="Ground speed in knots")
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    source: str = Field(..., description="ADSB or SOCIAL_INFERENCE")
    confidence_score: int = Field(default=50, ge=0, le=100)
    callsign: Optional[str] = Field(default=None, max_length=32)
    icao_hex: Optional[str] = Field(default=None, max_length=8)
    raw_text: Optional[str] = Field(default=None, description="Original social media text")
    metadata_json: Optional[dict[str, str]] = Field(default=None)

    @field_validator("source")
    @classmethod
    def _validate_source(cls, value: str) -> str:
        allowed: set[str] = {"ADSB", "SOCIAL_INFERENCE"}
        if value not in allowed:
            error_msg: str = f"source must be one of {allowed}"
            raise ValueError(error_msg)
        return value


class SightingCreate(SightingBase):
    """Schema for creating a new sighting."""


class SightingResponse(SightingBase):
    """Schema for returning a sighting to clients."""

    id: str
    timestamp: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class HeatmapPoint(BaseModel):
    """Aggregated point for heatmap rendering."""

    lat: float
    lon: float
    intensity: float = Field(..., ge=0.0, le=1.0)
    count: int = Field(..., ge=0)


class HeatmapResponse(BaseModel):
    """Collection of heatmap data points."""

    points: list[HeatmapPoint]
    total_sightings: int
    time_range_hours: int


class WebSocketMessage(BaseModel):
    """Typed message pushed over the live WebSocket feed."""

    event: str = Field(..., description="Event type: new_sighting | heartbeat | error")
    data: Optional[SightingResponse] = None
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    db_connected: bool
    redis_connected: bool
