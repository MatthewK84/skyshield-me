# SkyShield ME — Regional Detection Dashboard

Production-grade UAS/aircraft detection dashboard fusing ADS-B telemetry and social media sentiment analysis for the Middle East AOR.

## Architecture

```
┌────────────────┐     ┌──────────────┐     ┌────────────────┐
│  React/TS      │◄────│  FastAPI      │◄────│  PostgreSQL    │
│  Leaflet Map   │ WS  │  REST + WS   │     │  + PostGIS     │
│  React Query   │     │  Pydantic     │     │                │
└────────────────┘     └──────┬───────┘     └────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │  Celery + Redis   │
                    │  Beat Scheduler   │
                    └─────────┬─────────┘
                              │
               ┌──────────────┼──────────────┐
               │                             │
      ┌────────┴────────┐          ┌─────────┴────────┐
      │  ADS-B Exchange │          │  Telegram/Social  │
      │  Ingestor       │          │  Scraper          │
      │  (mock fallback)│          │  (Telethon)       │
      └─────────────────┘          └──────────────────┘
```

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env  # Edit with your API keys

# 2. Launch all services
docker compose up --build

# 3. Access
# Frontend:  http://localhost:5173
# API Docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/health
```

## Data Sources

### ADS-B Exchange
- Polls for aircraft in the ME bounding box (24°–38°N, 40°–56°E)
- Filters drone profile: altitude < 5,000 ft AND speed < 100 kts
- Falls back to synthetic mock data if no API key is configured

### Telegram Social Scraper
- Monitors configured channels for UAS-related keywords
- Weighted keyword scoring (e.g., "shahed" = 40, "buzzing" = 25)
- Regex geoparsing maps city names to coordinates
- FloodWaitError handling with exponential backoff
- Rate limiting: 3s between channels, 0.5s between messages

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/sightings/live` | Last 15 minutes, optional `?source=` filter |
| GET | `/api/v1/sightings/heatmap` | Aggregated density grid, `?hours=` lookback |
| WS | `/ws/live-feed` | Real-time push of new sightings |
| GET | `/health` | System health (DB + Redis) |

## Project Structure

```
/skyshield-me
├── docker-compose.yml
├── .env
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py              # FastAPI entry point
│       ├── core/                 # Settings, Celery config
│       ├── db/                   # SQLAlchemy models, session
│       ├── schemas/              # Pydantic request/response
│       ├── services/             # Business logic (DB ops)
│       ├── ingestors/            # ADS-B + Telegram modules
│       └── api/                  # REST + WebSocket routes
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        ├── App.tsx               # Root component
        ├── main.tsx              # React entry
        ├── components/
        │   ├── Map.tsx           # Leaflet map with layers
        │   ├── Sidebar.tsx       # Intel feed + filters
        │   └── Header.tsx        # Branding + status
        ├── hooks/
        │   ├── useWebSocket.ts   # Real-time WS connection
        │   └── useSightings.ts   # React Query data hooks
        ├── lib/
        │   └── api.ts            # Typed fetch client
        └── types/
            └── index.ts          # TypeScript interfaces
```

## Configuration

All configuration is via environment variables (see `.env`):

- `ADSB_API_KEY` — ADS-B Exchange API key (empty = mock mode)
- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` — Telegram app credentials
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis for caching
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — Task queue

## Development Notes

- Mock data generators activate automatically when API keys are absent
- All Python code uses strict type hints (no `Any`)
- All TypeScript uses strict mode with `noImplicitAny`
- WebSocket reconnects with exponential backoff (max 30s)
- Celery beat polls ADS-B every 30s, Telegram every 60s
