import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_analyst_or_above, require_any_authenticated
from app.db.database import get_db
from app.ml.inference import inference_service
from app.models.user import User
from app.services.emission_service import EmissionService
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
    """Forecast CO2e for the month right after the latest data for a series."""
    started = time.perf_counter()
    try:
        from app.services.company_service import CompanyService
        CompanyService.get_by_id(db, payload.company_id)  # 404 if missing
        records, _total = EmissionService.get_by_company(
            db, payload.company_id,
            scope=payload.scope,
            page_size=1000,
        )
        recent_records = [
            {
                "company_id": r.company_id,
                "scope": r.scope.value,
                "category": r.category.value,
                "co2_tonnes": r.co2_tonnes,
                "reporting_year": r.reporting_year,
                "reporting_month": r.reporting_month or 0,
            }
            for r in records
        ]
        return inference_service.predict_emissions(
            company_id=payload.company_id,
            scope=payload.scope.value,
            category=payload.category.value,
            reporting_year=payload.reporting_year,
            reporting_month=payload.reporting_month,
            recent_records=recent_records,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        _observe_latency("forecast", started)


@router.post("/anomalies", response_model=AnomalyScanResponse)
def detect_anomalies(
    payload: AnomalyScanRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """
    Score a company's emission records for anomalies.
    The full company history is fetched so that group statistics
    (z-score, ratio-to-median) are as stable as they were at training time.
    Only records for the requested year are returned.
    """
    started = time.perf_counter()
    try:
        records, _total = EmissionService.get_by_company(
            db, payload.company_id, page_size=5000
        )
        if not records:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for company {payload.company_id}",
            )
        if not any(r.reporting_year == payload.year for r in records):
            raise HTTPException(
                status_code=404,
                detail=f"No records for company {payload.company_id}, year {payload.year}",
            )

        records_data = [
            {
                "record_id": r.id,
                "company_id": r.company_id,
                "scope": r.scope.value,
                "category": r.category.value,
                "co2_tonnes": r.co2_tonnes,
                "reporting_year": r.reporting_year,
                "reporting_month": r.reporting_month or 0,
            }
            for r in records
        ]

        scored = inference_service.detect_anomalies(records_data)
        results = [r for r in scored if r["reporting_year"] == payload.year]
        anomaly_count = sum(1 for r in results if r["is_anomaly"])
        return {
            "company_id": payload.company_id,
            "year": payload.year,
            "total_records": len(results),
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_count / len(results), 3) if results else 0.0,
            "records": results,
        }
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        _observe_latency("anomalies", started)


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
def feature_importance(
    _: User = Depends(require_any_authenticated),
):
    """Challenger SHAP feature importance, pre-computed at train time."""
    return {"feature_importance": inference_service.get_feature_importance()}


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
