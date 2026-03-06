# SkyShield ME — Complete Deployment Guide
# GitHub Repository Setup + Railway Deployment

This guide assumes you are starting with the `skyshield-me.tar.gz` archive
downloaded from the previous conversation. Every click and command is
documented in order.

---

## Prerequisites

Before you begin, confirm you have the following:

- A GitHub account (free tier is fine)
- A Railway account at https://railway.com (Pro plan required for PostGIS — $5/month)
- Git installed locally (`git --version` to check)
- Node.js 18+ installed (`node --version` to check)
- A terminal (Terminal on Mac, PowerShell/WSL on Windows)

---

## PART 1: Get the Files Into GitHub

### Step 1 — Extract the Archive

Open a terminal and navigate to wherever you downloaded the archive:

```bash
cd ~/Downloads
mkdir -p ~/Projects/skyshield-me
tar -xzf skyshield-me.tar.gz -C ~/Projects/skyshield-me
cd ~/Projects/skyshield-me
```

If you are on Windows and do not have `tar`, use 7-Zip to extract it, then
`cd` into the resulting folder.

Verify the structure looks correct:

```bash
ls -la
```

You should see:

```
.env
.gitignore
README.md
DEPLOY_RAILWAY.md
docker-compose.yml
backend/
frontend/
```

### Step 2 — Remove Secrets from Tracking

The `.gitignore` already excludes `.env`, but double-check it is listed:

```bash
cat .gitignore | grep ".env"
```

You should see `.env` in the output. This prevents your API keys from being
pushed to GitHub.

### Step 3 — Create the GitHub Repository

Option A — GitHub CLI (if you have `gh` installed):

```bash
gh repo create skyshield-me --public --source=. --remote=origin
```

Option B — GitHub Web UI:

1. Go to https://github.com/new
2. Repository name: `skyshield-me`
3. Description: `Regional UAS detection dashboard — ADS-B + social media fusion`
4. Visibility: **Public** (Railway free templates require public repos; you can
   use Private if you have Railway Pro and connect via GitHub App)
5. Do NOT initialize with a README (you already have one)
6. Click **Create repository**
7. GitHub will show you a set of commands. Ignore them — use the ones below.

### Step 4 — Initialize Git and Push

From inside the `skyshield-me` directory:

```bash
git init
git branch -M main
git add .
git commit -m "Initial commit: SkyShield ME monorepo"
```

Now connect to your GitHub repo (replace YOUR_USERNAME):

```bash
git remote add origin https://github.com/YOUR_USERNAME/skyshield-me.git
git push -u origin main
```

If prompted for credentials, enter your GitHub username and a Personal Access
Token (not your password). You can create a token at:
https://github.com/settings/tokens → Generate new token (classic) → check `repo` scope.

### Step 5 — Verify on GitHub

Go to `https://github.com/YOUR_USERNAME/skyshield-me`. You should see all files,
with the README rendered at the bottom. Confirm these exist:

- `backend/railway.toml`
- `backend/railway-worker.toml`
- `backend/railway-beat.toml`
- `frontend/railway.toml`
- `docker-compose.yml`

GitHub is done. Do not touch it again until after Railway is configured.

---

## PART 2: Deploy on Railway

Railway does not use `docker-compose.yml`. You will create 6 individual
services inside one Railway project, all pointing to the same GitHub repo
but with different root directories and config files.

The services are:

| # | Service Name       | Type            | Root Dir    | Config File Path                |
|---|--------------------|-----------------|-------------|----------------------------------|
| 1 | PostGIS            | Database (template) | —       | —                                |
| 2 | Redis              | Database (template) | —       | —                                |
| 3 | backend-api        | GitHub repo     | `/backend`  | `/backend/railway.toml`          |
| 4 | celery-worker      | GitHub repo     | `/backend`  | `/backend/railway-worker.toml`   |
| 5 | celery-beat        | GitHub repo     | `/backend`  | `/backend/railway-beat.toml`     |
| 6 | frontend           | GitHub repo     | `/frontend` | `/frontend/railway.toml`         |

### Step 6 — Create a Railway Project

1. Go to https://railway.com/dashboard
2. Click **New Project**
3. Select **Empty Project**
4. A blank canvas opens. This is your project workspace.

### Step 7 — Add the PostGIS Database

1. On the canvas, click the **+ New** button (top-right corner)
2. Select **Template**
3. In the search bar, type `PostGIS`
4. Click the **PostGIS** template (by Railway, described as "PostgreSQL DB enabled with PostGIS")
5. Click **Deploy Template**
6. Wait for the service to show a green checkmark (usually 30–60 seconds)
7. Click on the PostGIS service on the canvas
8. Click the **Variables** tab
9. You will see auto-generated variables including `DATABASE_URL`, `PGUSER`,
   `PGPASSWORD`, etc. Do not change these — you will reference them later.
10. Click the **Data** tab (or connect via the **Connect** button)
11. In the SQL console, run:
    ```sql
    CREATE EXTENSION IF NOT EXISTS postgis;
    ```
    This enables spatial queries. You should see `CREATE EXTENSION` as output.

### Step 8 — Add Redis

1. Click **+ New** on the canvas again
2. Select **Database**
3. Choose **Add Redis**
4. Wait for the green checkmark
5. Click on the Redis service
6. Note the **Variables** tab shows `REDIS_URL` among others

### Step 9 — Deploy the Backend API

1. Click **+ New** on the canvas
2. Select **Empty Service**
3. A new unnamed service appears on the canvas
4. Right-click the service → **Update Info** → rename it to `backend-api`
5. Click on `backend-api` to open the service panel
6. Click the **Settings** tab
7. Under **Service Source**, click **Connect Repo**
8. If you have not connected your GitHub account to Railway yet:
   - Click **Configure GitHub App**
   - Authorize Railway to access your repositories
   - Select the `skyshield-me` repository (or grant access to all repos)
   - Return to Railway
9. Select the `skyshield-me` repository from the dropdown
10. Under **Root Directory**, enter: `/backend`
11. Under **Config File Path** (may be labeled "Config as Code"), enter: `/backend/railway.toml`
12. Under **Watch Paths**, enter: `/backend/**`
13. Click **Deploy** (⇧ Enter) to save changes — the build will start but will likely fail because
    environment variables are not set yet. That is expected.

Now add the variables:

14. Click the **Variables** tab
15. Click **New Variable** for each of the following. When typing the value,
    Railway's autocomplete dropdown will appear — use it to select references:

| Variable Name           | Value                                        |
|-------------------------|----------------------------------------------|
| `DATABASE_URL`          | `${{PostGIS.DATABASE_URL}}`                  |
| `REDIS_URL`             | `${{Redis.REDIS_URL}}`                       |
| `CELERY_BROKER_URL`     | `${{Redis.REDIS_URL}}`                       |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}`                       |
| `APP_ENV`               | `production`                                 |
| `LOG_LEVEL`             | `INFO`                                       |
| `CORS_ORIGINS`          | `https://*.up.railway.app`                   |
| `ADSB_API_KEY`          | *(leave empty for mock data, or paste your key)* |
| `TELEGRAM_API_ID`       | *(leave empty for mock data, or paste your ID)*  |
| `TELEGRAM_API_HASH`     | *(leave empty for mock data)*                |

To type a reference variable like `${{PostGIS.DATABASE_URL}}`:
- Click **New Variable**
- In the **Value** field, start typing `${{` — a dropdown will appear
- Select `PostGIS` from the service list
- Select `DATABASE_URL` from the variable list
- Railway fills in `${{PostGIS.DATABASE_URL}}` for you

16. Click **Deploy** (⇧ Enter) to apply the variables and trigger a new build
17. Wait for the build to complete (2–4 minutes). Watch the **Deployments** tab for logs.
18. If the build succeeds, go to **Settings** → **Networking** → click **Generate Domain**
19. Railway generates a public URL like `backend-api-production-xxxx.up.railway.app`
20. **Copy this URL** — you need it for the frontend and for CORS.

Now go back to the Variables tab and update CORS_ORIGINS to include the exact
frontend domain (you will get this in Step 12 — come back and update it then).

### Step 10 — Deploy the Celery Worker

1. Click **+ New** → **Empty Service**
2. Rename to `celery-worker`
3. Click on it → **Settings** tab
4. **Connect Repo** → select `skyshield-me`
5. **Root Directory**: `/backend`
6. **Config File Path**: `/backend/railway-worker.toml`
7. **Watch Paths**: `/backend/**`
8. Go to the **Variables** tab and add:

| Variable Name           | Value                          |
|-------------------------|--------------------------------|
| `DATABASE_URL`          | `${{PostGIS.DATABASE_URL}}`    |
| `REDIS_URL`             | `${{Redis.REDIS_URL}}`         |
| `CELERY_BROKER_URL`     | `${{Redis.REDIS_URL}}`         |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}`         |

9. Click **Deploy** (⇧ Enter)
10. This service does NOT need a public domain. It runs in the background.
11. Wait for the green checkmark. Check logs — you should see
    `celery@... ready` or similar Celery startup messages.

### Step 11 — Deploy the Celery Beat Scheduler

1. Click **+ New** → **Empty Service**
2. Rename to `celery-beat`
3. Click on it → **Settings**
4. **Connect Repo** → select `skyshield-me`
5. **Root Directory**: `/backend`
6. **Config File Path**: `/backend/railway-beat.toml`
7. **Watch Paths**: `/backend/**`
8. **Variables** tab — add:

| Variable Name           | Value                          |
|-------------------------|--------------------------------|
| `CELERY_BROKER_URL`     | `${{Redis.REDIS_URL}}`         |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}`         |

9. Click **Deploy** (⇧ Enter)
10. No public domain needed. Check logs for `celery beat v5.x.x ... ready`.

### Step 12 — Deploy the Frontend

1. Click **+ New** → **Empty Service**
2. Rename to `frontend`
3. Click on it → **Settings**
4. **Connect Repo** → select `skyshield-me`
5. **Root Directory**: `/frontend`
6. **Config File Path**: `/frontend/railway.toml`
7. **Watch Paths**: `/frontend/**`
8. **Variables** tab — add:

| Variable Name   | Value                                                       |
|-----------------|-------------------------------------------------------------|
| `VITE_API_URL`  | `https://backend-api-production-xxxx.up.railway.app`        |
| `VITE_WS_URL`   | `wss://backend-api-production-xxxx.up.railway.app`          |

Replace `backend-api-production-xxxx.up.railway.app` with the actual backend
URL you copied in Step 9.20. Note `VITE_WS_URL` uses `wss://` (secure WebSocket)
because Railway enforces HTTPS on all public domains.

9. Click **Deploy** (⇧ Enter)
10. Wait for the build (1–2 minutes)
11. Go to **Settings** → **Networking** → **Generate Domain**
12. Railway gives you something like `frontend-production-yyyy.up.railway.app`
13. **Copy this URL**

### Step 13 — Update Backend CORS with the Frontend Domain

1. Click on the `backend-api` service on the canvas
2. Go to the **Variables** tab
3. Find `CORS_ORIGINS`
4. Update the value to: `https://frontend-production-yyyy.up.railway.app`
   (use the actual domain from Step 12.12)
5. Click **Deploy** (⇧ Enter) to trigger a redeploy with the updated CORS

### Step 14 — Verify Everything Works

Open your frontend URL in a browser:

```
https://frontend-production-yyyy.up.railway.app
```

You should see:
- The SkyShield ME header with "CONNECTED" status and a UTC clock
- A dark map centered on the Middle East
- Blue (ADS-B) and red (Social) markers appearing
- The sidebar Live Intel Feed populating with mock data

Test the backend API directly:

```
https://backend-api-production-xxxx.up.railway.app/health
```

You should see JSON like:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "db_connected": true,
  "redis_connected": true
}
```

Test the API docs:

```
https://backend-api-production-xxxx.up.railway.app/docs
```

This opens the interactive Swagger UI with all endpoints.

---

## PART 3: Verify Service Health

### Check Each Service on the Railway Canvas

Your canvas should show 6 services. Each should have a green indicator:

```
┌─────────────┐    ┌─────────────┐
│   PostGIS   │    │    Redis    │
│   (green)   │    │   (green)   │
└──────┬──────┘    └──────┬──────┘
       │                  │
       └────────┬─────────┘
                │
       ┌────────┴────────┐
       │   backend-api   │
       │   (green, URL)  │
       └────────┬────────┘
                │
    ┌───────────┼───────────┐
    │                       │
┌───┴──────────┐  ┌─────────┴──┐
│ celery-worker│  │ celery-beat │
│   (green)    │  │   (green)   │
└──────────────┘  └────────────┘

       ┌─────────────┐
       │   frontend   │
       │ (green, URL) │
       └─────────────┘
```

### If a Service Shows Red (Failed Build)

1. Click on the service
2. Click the **Deployments** tab
3. Click the failed deployment to see build logs
4. Common issues:
   - **"railway.toml not found"**: The Config File Path must be an absolute path
     from the repo root, e.g., `/backend/railway.toml`, not just `railway.toml`
   - **Database connection refused**: The `DATABASE_URL` reference variable is
     not resolving. Click into the value field and verify it shows
     `${{PostGIS.DATABASE_URL}}`
   - **Module not found**: The Root Directory may be wrong. It should be
     `/backend` or `/frontend` — not `/skyshield-me/backend`
   - **"No start command found"**: Verify the Config File Path is set correctly
     so Railway reads the `railway.toml` with the `startCommand` directive
   - **PostGIS extension error**: You forgot to run `CREATE EXTENSION postgis;`
     in Step 7.11. Go back to the PostGIS service Data tab and run it.

---

## PART 4: Ongoing Maintenance

### Pushing Updates

Any `git push` to the `main` branch automatically triggers a rebuild of the
services whose watch paths match the changed files:

```bash
# Edit some backend code
git add .
git commit -m "Fix sighting confidence threshold"
git push origin main
```

Railway will only rebuild services with matching watch paths:
- Changes in `/backend/**` → rebuilds `backend-api`, `celery-worker`, `celery-beat`
- Changes in `/frontend/**` → rebuilds `frontend`

### Viewing Logs

1. Click any service on the canvas
2. Click the **Deployments** tab
3. Click the active deployment
4. Logs stream in real-time

### Scaling

In the service **Settings**, you can:
- Increase memory/CPU allocation
- Add horizontal replicas (Pro plan)
- Configure auto-restart policies

### Custom Domain

1. Click on the `frontend` service → **Settings** → **Networking**
2. Click **Add Custom Domain**
3. Enter your domain (e.g., `skyshield.yourdomain.com`)
4. Railway provides CNAME records — add them to your DNS provider
5. Wait for DNS propagation (usually 5–30 minutes)
6. Update `CORS_ORIGINS` on the backend to include the new domain
7. Update `VITE_API_URL` and `VITE_WS_URL` on the frontend if the backend
   also gets a custom domain

---

## Quick Reference: All Environment Variables

### backend-api

```
DATABASE_URL          = ${{PostGIS.DATABASE_URL}}
REDIS_URL             = ${{Redis.REDIS_URL}}
CELERY_BROKER_URL     = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND = ${{Redis.REDIS_URL}}
APP_ENV               = production
LOG_LEVEL             = INFO
CORS_ORIGINS          = https://frontend-production-yyyy.up.railway.app
ADSB_API_KEY          = (optional)
TELEGRAM_API_ID       = (optional)
TELEGRAM_API_HASH     = (optional)
```

### celery-worker

```
DATABASE_URL          = ${{PostGIS.DATABASE_URL}}
REDIS_URL             = ${{Redis.REDIS_URL}}
CELERY_BROKER_URL     = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND = ${{Redis.REDIS_URL}}
```

### celery-beat

```
CELERY_BROKER_URL     = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND = ${{Redis.REDIS_URL}}
```

### frontend

```
VITE_API_URL          = https://backend-api-production-xxxx.up.railway.app
VITE_WS_URL           = wss://backend-api-production-xxxx.up.railway.app
```
