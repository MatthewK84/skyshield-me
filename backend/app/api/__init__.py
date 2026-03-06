"""
SkyShield ME — API Routes.

Defines REST endpoints for sighting retrieval and a WebSocket
endpoint for real-time live-feed push to connected frontends.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas import (
    HeatmapResponse,
    SightingResponse,
    WebSocketMessage,
)
from app.services import (
    get_heatmap_data,
    get_live_sightings,
    get_total_sightings_count,
)

logger: logging.Logger = logging.getLogger(__name__)
router: APIRouter = APIRouter(prefix="/api/v1", tags=["sightings"])

# ─── WebSocket Connection Manager ────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live feed broadcasting."""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._active.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self._active))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a disconnected WebSocket client."""
        if websocket in self._active:
            self._active.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self._active))

    async def broadcast(self, message: WebSocketMessage) -> None:
        """Push a message to all connected WebSocket clients."""
        payload: str = message.model_dump_json()
        stale_connections: list[WebSocket] = []

        for connection in self._active:
            try:
                await connection.send_text(payload)
            except (WebSocketDisconnect, RuntimeError):
                stale_connections.append(connection)

        for stale in stale_connections:
            self.disconnect(stale)

    @property
    def active_count(self) -> int:
        """Return number of active WebSocket connections."""
        return len(self._active)


ws_manager = ConnectionManager()


# ─── REST Endpoints ──────────────────────────────────────────────

@router.get("/sightings/live", response_model=list[SightingResponse])
async def get_live(
    source: Optional[str] = Query(default=None, description="Filter: ADSB or SOCIAL_INFERENCE"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[SightingResponse]:
    """
    Retrieve sightings from the last 15 minutes.

    Optionally filtered by source type. Returns newest first.
    """
    sightings = await get_live_sightings(db, source_filter=source, limit=limit)

    results: list[SightingResponse] = [
        SightingResponse.model_validate(s) for s in sightings
    ]
    return results


@router.get("/sightings/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    hours: int = Query(default=24, ge=1, le=720, description="Lookback window in hours"),
    precision: int = Query(default=2, ge=1, le=5, description="Grid decimal precision"),
    db: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    """
    Retrieve aggregated heatmap data for historical sighting density.

    Grid precision controls cell size: 2 = ~1km, 3 = ~100m.
    """
    points = await get_heatmap_data(db, hours=hours, grid_precision=precision)
    total: int = await get_total_sightings_count(db, hours=hours)

    return HeatmapResponse(
        points=points,
        total_sightings=total,
        time_range_hours=hours,
    )


# ─── WebSocket Live Feed ────────────────────────────────────────

@router.websocket("/ws/live-feed")
async def websocket_live_feed(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time sighting push.

    Polls the database every 5 seconds for new sightings
    and broadcasts them to all connected clients.
    Sends heartbeat every 30 seconds to keep connections alive.
    """
    await ws_manager.connect(websocket)
    last_check: datetime = datetime.now(tz=timezone.utc)
    heartbeat_counter: int = 0

    try:
        while True:
            await asyncio.sleep(5.0)
            heartbeat_counter += 1

            try:
                # Check for new sightings since last poll
                async for db in get_db():
                    new_sightings = await get_live_sightings(db, limit=50)

                    for sighting in new_sightings:
                        if sighting.created_at > last_check:
                            msg = WebSocketMessage(
                                event="new_sighting",
                                data=SightingResponse.model_validate(sighting),
                                timestamp=datetime.now(tz=timezone.utc),
                            )
                            await ws_manager.broadcast(msg)

                    last_check = datetime.now(tz=timezone.utc)

            except Exception as exc:
                logger.error("WebSocket poll error: %s", exc)

            # Heartbeat every ~30 seconds (6 iterations * 5s)
            if heartbeat_counter >= 6:
                heartbeat = WebSocketMessage(
                    event="heartbeat",
                    message="alive",
                    timestamp=datetime.now(tz=timezone.utc),
                )
                await ws_manager.broadcast(heartbeat)
                heartbeat_counter = 0

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WebSocket fatal error: %s", exc)
        ws_manager.disconnect(websocket)
