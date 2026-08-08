from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    companies,
    emissions,
    predictions,
    rag,
    tasks,
    websocket,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(emissions.router)
api_router.include_router(tasks.router)
api_router.include_router(predictions.router)
api_router.include_router(rag.router)
api_router.include_router(websocket.router)