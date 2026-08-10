# Deployment Guide

CarbonSense is deployed on **Vercel** (frontend + serverless API) with **Neon Postgres**.

## Live URLs

| Service | URL |
|---|---|
| Frontend | https://frontend-two-lemon-xx0y85u0vn.vercel.app |
| API | https://carbonsense-api.vercel.app |
| API docs | https://carbonsense-api.vercel.app/docs |

**Demo admin:** `admin@carbonsense.fr` / `Admin1234`

## Frontend → Vercel

Project: `frontend` (root directory: `frontend/`)

### Environment variables (Production)

| Variable | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://carbonsense-api.vercel.app` |
| `VITE_WS_BASE_URL` | `wss://carbonsense-api.vercel.app` |
| `VITE_APP_NAME` | `CarbonSense` |

### Deploy

```bash
cd frontend
vercel --prod
```

## Backend → Vercel (serverless)

Project: `carbonsense-api` (repo root)

Uses `api/index.py` (Mangum ASGI wrapper) and `vercel.json` with `@vercel/python`.

### Database → Neon (via Vercel Marketplace)

1. Accept Neon terms in Vercel dashboard.
2. `vercel integration add neon` (or connect existing resource).
3. Connect the Neon resource to `carbonsense-api` — this sets `DATABASE_URL` and `DATABASE_URL_UNPOOLED`.

Run migrations against Neon (use unpooled URL):

```bash
# Set DATABASE_URL to DATABASE_URL_UNPOOLED from Vercel env, then:
alembic upgrade head
python scripts/seed_admin.py
python scripts/seed_data.py
```

### Required environment variables (Production)

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Set by Neon integration (pooled) |
| `DATABASE_URL_UNPOOLED` | Set by Neon integration (migrations) |
| `SECRET_KEY` | Strong random string for JWT signing |
| `CORS_ORIGINS` | Comma-separated frontend URLs, e.g. `https://frontend-two-lemon-xx0y85u0vn.vercel.app,http://localhost:3000` |

Optional: add **Upstash Redis** via Vercel Marketplace for cache and rate-limit persistence (`REDIS_URL`).

### Deploy

```bash
vercel --prod
```

### Vercel serverless limitations

These features require a long-running process (Docker/Railway/K8s) and are **disabled on Vercel**:

- ML predictions & RAG chat
- WebSockets (real-time alerts)
- Kafka consumer
- Celery background tasks

REST endpoints work: auth, companies, emissions (read/write), tasks (polling).

## Backend → Railway (full stack)

For ML, WebSockets, Kafka, and Celery, deploy the Docker image on Railway:

1. Push the repo to GitHub.
2. Create a Railway project from the repo (detects `Dockerfile`).
3. Add PostgreSQL and Redis plugins.
4. Set environment variables from `.env.docker`, using Railway connection strings.
5. Set `CORS_ORIGINS` to your Vercel frontend URL.

See `docker-compose.yml` for the full local stack.

## GitHub CI/CD

Set these secrets in GitHub → Settings → Secrets:

| Secret | How to get it |
|---|---|
| `VERCEL_TOKEN` | vercel.com → Account Settings → Tokens |
| `VERCEL_ORG_ID` | `frontend/.vercel/project.json` → `orgId` |
| `VERCEL_PROJECT_ID` | `frontend/.vercel/project.json` → `projectId` |
| `VITE_API_BASE_URL` | `https://carbonsense-api.vercel.app` |
| `VITE_WS_BASE_URL` | `wss://carbonsense-api.vercel.app` |

Every push to `main` auto-deploys via `.github/workflows/ci.yml`.
