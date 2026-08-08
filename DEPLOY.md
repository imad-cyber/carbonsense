# Deployment Guide

## Frontend → Vercel

### 1. Install Vercel CLI
```bash
npm i -g vercel
```

### 2. Link the project
```bash
cd frontend
vercel link
# Select: Add to existing project (or create new)
# Project name: carbonsense-frontend
# Root directory: frontend/   ← IMPORTANT
```

### 3. Set environment variables in Vercel dashboard
Go to vercel.com → carbonsense-frontend → Settings → Environment Variables:

| Variable | Value |
|---|---|
| VITE_API_BASE_URL | https://your-backend.railway.app |
| VITE_WS_BASE_URL | wss://your-backend.railway.app |
| VITE_APP_NAME | CarbonSense |

### 4. Set GitHub secrets for CI/CD
In GitHub repo → Settings → Secrets and variables → Actions:

| Secret | How to get it |
|---|---|
| VERCEL_TOKEN | vercel.com → Account Settings → Tokens |
| VERCEL_ORG_ID | `cat frontend/.vercel/project.json` → orgId |
| VERCEL_PROJECT_ID | `cat frontend/.vercel/project.json` → projectId |
| VITE_API_BASE_URL | your Railway backend URL |
| VITE_WS_BASE_URL | wss:// version of the same URL |

### 5. Deploy manually first
```bash
cd frontend
vercel --prod
```

### 6. After this — every push to main auto-deploys. ✅

## Backend → Railway

See `docker-compose.yml` for the full local stack.

For Railway:
1. Push the repo to GitHub.
2. Create a Railway project from the repo (it detects the `Dockerfile`).
3. Add PostgreSQL and Redis plugins.
4. Set environment variables from `.env.docker`, swapping hostnames for the
   Railway plugin connection strings and setting a strong `SECRET_KEY`.
5. Set `CORS_ORIGINS` to your Vercel frontend URL (e.g. `https://carbonsense.vercel.app`).
