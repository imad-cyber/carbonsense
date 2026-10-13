from fastapi import APIRouter

from app.api.v1.endpoints import (
    activity_emissions, auth, companies, emission_factors, emissions, predictions,
)
from app.core.config import settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(emission_factors.router)
api_router.include_router(activity_emissions.router)   # before emissions, so /from-activity wins
api_router.include_router(emissions.router)
api_router.include_router(predictions.router)

def _include_experimental() -> None:
    if settings.ENABLE_EXPERIMENTAL:
        from app.api.v1.endpoints import rag, tasks, websocket

        api_router.include_router(tasks.router)
        api_router.include_router(rag.router)
        api_router.include_router(websocket.router)


_include_experimental()