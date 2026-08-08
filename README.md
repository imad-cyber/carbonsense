# CarbonSense — AI-Powered CSRD/ESG Carbon Intelligence Platform

[![CI/CD](https://github.com/imad-cyber/carbonsense/actions/workflows/ci.yml/badge.svg)](https://github.com/imad-cyber/carbonsense/actions/workflows/ci.yml)
[![Frontend](https://github.com/imad-cyber/carbonsense/actions/workflows/frontend.yml/badge.svg)](https://github.com/imad-cyber/carbonsense/actions/workflows/frontend.yml)
[![Deployed on Vercel](https://img.shields.io/badge/deployed%20on-Vercel-black)](https://carbonsense.vercel.app)

CarbonSense tracks Scope 1, 2 and 3 greenhouse gas emissions for CSRD compliance reporting.
It forecasts emissions with XGBoost, detects anomalies with Isolation Forest, explains every
prediction with SHAP, and generates ESRS E1 disclosure narratives via a LangChain RAG pipeline.

## Architecture

```
                        ┌────────────────────────────────────────────┐
                        │              React Frontend                │
                        │        (Vite + TS + Tailwind, Vercel)      │
                        └────────┬─────────────────────┬─────────────┘
                            REST / SSE            WebSocket
                                 │                     │
┌────────────┐          ┌────────▼─────────────────────▼─────────────┐
│ Prometheus │◄─scrape──┤              FastAPI  (/api/v1)            │
│  +Grafana  │          │  Auth · Companies · Emissions · Predictions│
└────────────┘          │        RAG · Tasks · WebSockets            │
                        └──┬───────┬──────────┬──────────┬───────────┘
                           │       │          │          │
                     ┌─────▼──┐ ┌──▼───┐ ┌────▼────┐ ┌───▼────────┐
                     │Postgres│ │Redis │ │  FAISS  │ │   Kafka    │
                     │  (SQL) │ │cache │ │ vectors │ │  events    │
                     └────────┘ └──┬───┘ └────┬────┘ └───┬────────┘
                                   │          │          │
                        ┌──────────▼──────────▼──────────▼──────────┐
                        │   Celery Workers (bulk, reports, retrain) │
                        │   XGBoost · IsolationForest · SHAP · LLM  │
                        └──────────┬────────────────────┬───────────┘
                                   │                    │
                             ┌─────▼─────┐        ┌─────▼─────┐
                             │  MLflow   │        │  Airflow  │
                             │ tracking  │        │   DAGs    │
                             └───────────┘        └───────────┘
```

## Quick Start (local)

```bash
git clone https://github.com/imad-cyber/carbonsense.git && cd carbonsense
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # then edit values
alembic upgrade head
uvicorn app.main:app --reload
```

Or run everything in Docker:

```bash
docker-compose up -d
docker-compose exec api python scripts/seed_admin.py
docker-compose exec api python scripts/generate_training_data.py
docker-compose exec api python scripts/train_models.py
```

Frontend:

```bash
cd frontend && npm install && npm run dev            # http://localhost:3000
```

## Key Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Create an account | — |
| POST | `/api/v1/auth/login` | Get a JWT | — |
| GET | `/api/v1/companies/` | List companies (paginated) | any |
| POST | `/api/v1/emissions/` | Create emission record | analyst+ |
| GET | `/api/v1/emissions/summary/{id}/{year}` | Scope 1/2/3 totals (cached) | any |
| POST | `/api/v1/emissions/bulk/{id}` | Async bulk upload (202 + task id) | analyst+ |
| POST | `/api/v1/predictions/forecast` | XGBoost forecast + SHAP explanation | any |
| POST | `/api/v1/predictions/anomalies` | Isolation Forest anomaly scan | any |
| GET | `/api/v1/predictions/feature-importance` | Global SHAP importance | any |
| POST | `/api/v1/predictions/retrain` | Queue model retraining | analyst+ |
| POST | `/api/v1/rag/ingest/regulatory` | Ingest CSRD/ESRS texts into FAISS | analyst+ |
| POST | `/api/v1/rag/chat` | RAG Q&A (SSE streaming) | any |
| GET | `/api/v1/rag/report/{id}/{year}` | Stream CSRD E1 report (SSE) | any |
| POST | `/api/v1/rag/search` | Similarity search over regulations | any |
| GET | `/api/v1/tasks/{task_id}` | Poll Celery task status | any |
| WS | `/api/v1/ws/live/{company_id}?token=` | Live emission feed + scoring | JWT |
| GET | `/metrics` | Prometheus metrics | — |
| GET | `/health` | Health check | — |

Full interactive documentation: **http://localhost:8000/docs**

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API | FastAPI + Pydantic v2 | REST/SSE/WebSocket endpoints |
| Database | PostgreSQL + SQLAlchemy + Alembic | Persistent storage + migrations |
| Cache | Redis | Cache-aside summaries, report cache, rate limits |
| Queue | Celery + Redis | Bulk uploads, report generation, retraining |
| Streaming | Kafka | Real-time emission events + anomaly alerts |
| Orchestration | Airflow | Daily pipeline + weekly retraining DAGs |
| ML | XGBoost, scikit-learn, SHAP | Forecasting, anomaly detection, explainability |
| ML tracking | MLflow | Experiment tracking + model versioning |
| LLM/RAG | LangChain + OpenAI + FAISS | Regulatory Q&A + CSRD report generation |
| Observability | Prometheus + Grafana | Business + infra metrics |
| Frontend | React 18 + TypeScript + Vite + Tailwind | Dashboard SPA |
| Deploy | Docker Compose, Kubernetes, Vercel | Local stack, prod orchestration, frontend |

## Running Tests

```bash
pytest tests/ -v            # Redis-dependent tests skip automatically if Redis is down
```

## Service UIs

| Service | URL | Credentials |
|---|---|---|
| Swagger | http://localhost:8000/docs | — |
| MLflow | http://localhost:5000 | — |
| Flower (Celery) | http://localhost:5555 | — |
| Grafana | http://localhost:3001 | admin / carbonsense123 |
| Airflow | http://localhost:8080 | admin / admin |
| Prometheus | http://localhost:9090 | — |

Run Airflow standalone (without Docker): `airflow webserver & airflow scheduler`
Run MLflow standalone: `mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5000`

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | — (required) |
| `SECRET_KEY` | JWT signing key | — (required) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | `30` |
| `REDIS_URL` | Redis cache | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery Redis DBs | `redis://localhost:6379/1,2` |
| `MLFLOW_TRACKING_URI` | MLflow backend | `sqlite:///mlflow.db` |
| `MODEL_DIR` | Trained model directory | `models` |
| `MIN_FORECAST_R2` | Model quality gate threshold | `0.70` |
| `OPENAI_API_KEY` | Enables RAG/LLM features | empty (RAG returns 503) |
| `LLM_MODEL` / `EMBEDDING_MODEL` | OpenAI models | `gpt-4o-mini` / `text-embedding-3-small` |
| `VECTOR_STORE_PATH` | FAISS index directory | `vector_store` |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker (empty = disabled) | `localhost:9092` |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `http://localhost:3000` |

## Graceful Degradation

The API starts and serves requests even when optional infrastructure is down:
- **Redis down** → cache misses logged as warnings, requests still served from DB
- **Kafka down** → events silently skipped, HTTP requests unaffected
- **No OpenAI key** → RAG endpoints return `503` with a clear message
- **Models untrained** → prediction endpoints return `503` with instructions
