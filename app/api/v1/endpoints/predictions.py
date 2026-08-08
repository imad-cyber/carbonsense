import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_analyst_or_above, require_any_authenticated
from app.db.database import get_db
from app.ml.inference import inference_service
from app.models.user import User
from app.schemas.emission import TaskStatusResponse
from app.schemas.prediction import (
    AnomalyScanRequest,
    AnomalyScanResponse,
    FeatureImportanceResponse,
    ForecastRequest,
    ForecastResponse,
    ModelStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["Predictions"])


def _observe_latency(endpoint: str, started_at: float) -> None:
    """Record prediction latency — metric failures must never break requests."""
    try:
        from app.core.metrics import prediction_latency_seconds
        prediction_latency_seconds.labels(endpoint=endpoint).observe(
            time.perf_counter() - started_at
        )
    except Exception:  # noqa: BLE001
        pass


@router.get("/status", response_model=ModelStatusResponse)
def model_status(_: User = Depends(require_any_authenticated)):
    """Report which ML models are trained and available for inference."""
    return inference_service.status()


@router.post("/forecast", response_model=ForecastResponse)
def forecast_emissions(
    payload: ForecastRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """
    Forecast CO2 emissions for a company/scope/category/month
    using the trained XGBoost model, with a SHAP explanation of
    what drove the prediction.
    """
    started = time.perf_counter()
    try:
        result = inference_service.predict_emissions(
            db,
            company_id=payload.company_id,
            scope=payload.scope.value,
            category=payload.category.value,
            reporting_year=payload.reporting_year,
            reporting_month=payload.reporting_month,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    finally:
        _observe_latency("forecast", started)
    return result


@router.post("/anomalies", response_model=AnomalyScanResponse)
def detect_anomalies(
    payload: AnomalyScanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """
    Scan all emission records of a company for a given year with the
    Isolation Forest anomaly detector. Returns per-record scores and
    severity levels for flagged records.
    """
    started = time.perf_counter()
    try:
        return inference_service.detect_anomalies(db, payload.company_id, payload.year)
    finally:
        _observe_latency("anomalies", started)


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
def feature_importance(
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """Global SHAP feature importance for the forecasting model (top 15)."""
    return inference_service.get_feature_importance(db)


@router.post(
    "/retrain",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_retraining(_: User = Depends(require_analyst_or_above)):
    """
    Queue model retraining as a background Celery task.
    Poll /api/v1/tasks/{task_id} for progress.
    """
    from app.worker.tasks import retrain_models

    task = retrain_models.delay()
    return TaskStatusResponse(
        task_id=task.id,
        status="queued",
        message=f"Model retraining queued. Poll /api/v1/tasks/{task.id} for status.",
    )
