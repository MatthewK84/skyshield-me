"""
SkyShield ME — Celery Application Configuration.

Defines the Celery app, periodic beat schedule for ADS-B polling
and Telegram scraping, and task autodiscovery.
"""

from __future__ import annotations

from celery import Celery

from app.core import get_settings, ADSB_POLL_INTERVAL_SECONDS, TELEGRAM_POLL_INTERVAL_SECONDS

settings = get_settings()

celery_app = Celery(
    "skyshield_me",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ─── Upstash TLS Support ────────────────────────────────────────
if settings.is_redis_tls():
    import ssl

    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_REQUIRED},
    )

# ─── Periodic Tasks (Beat Schedule) ─────────────────────────────
celery_app.conf.beat_schedule = {
    "poll-adsb-exchange": {
        "task": "app.ingestors.adsb_ingestor.poll_adsb",
        "schedule": float(ADSB_POLL_INTERVAL_SECONDS),
    },
    "poll-telegram-channels": {
        "task": "app.ingestors.telegram_ingestor.poll_telegram",
        "schedule": float(TELEGRAM_POLL_INTERVAL_SECONDS),
    },
}

# ─── Explicit task imports (autodiscover doesn't work reliably) ──
import app.ingestors.adsb_ingestor  # noqa: F401
import app.ingestors.telegram_ingestor  # noqa: F401
