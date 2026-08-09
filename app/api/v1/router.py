import os

from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    companies,
    emissions,
    tasks,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(emissions.router)
api_router.include_router(tasks.router)

# Vercel serverless: no background workers, WebSockets, or heavy ML/RAG deps
_on_vercel = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))

if not _on_vercel:
    from app.api.v1.endpoints import predictions, rag, websocket

    api_router.include_router(predictions.router)
    api_router.include_router(rag.router)
    api_router.include_router(websocket.router)