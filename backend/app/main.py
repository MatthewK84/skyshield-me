"""
SkyShield ME — FastAPI Application Entry Point.

Configures the ASGI application with CORS, database lifecycle hooks,
route registration, and health check endpoint.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.core import get_settings
from app.db import Base, engine
from app.schemas import HealthResponse

settings = get_settings()

# ─── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger("skyshield_me")


# ─── Lifespan (startup / shutdown) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle manager.

    Creates database tables on startup and disposes the engine on shutdown.
    """
    logger.info("SkyShield ME starting up — env=%s", settings.app_env)

    # Create tables (use Alembic for production migrations)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    yield

    logger.info("SkyShield ME shutting down")
    await engine.dispose()


# ─── Application Factory ────────────────────────────────────────
app = FastAPI(
    title="SkyShield ME",
    description=(
        "Regional UAS/aircraft detection dashboard fusing ADS-B telemetry "
        "and social media sentiment analysis for the Middle East AOR."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────
# Railway generates *.up.railway.app domains — use regex for wildcard support
cors_origins: list[str] = settings.get_cors_list()
has_wildcard: bool = any("*" in origin for origin in cors_origins)

if has_wildcard:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https://.*\.up\.railway\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ─── Routes ──────────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """System health check — verifies DB and Redis connectivity."""
    db_ok: bool = False
    redis_ok: bool = False

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1"),
            )
            db_ok = True
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)

    # Check Redis
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.redis_url, decode_responses=True)
        redis_ok = r.ping()
        r.close()
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)

    return HealthResponse(
        status="healthy" if (db_ok and redis_ok) else "degraded",
        version="1.0.0",
        db_connected=db_ok,
        redis_connected=redis_ok,
    )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Root endpoint — API info."""
    return {
        "service": "SkyShield ME",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational",
    }
