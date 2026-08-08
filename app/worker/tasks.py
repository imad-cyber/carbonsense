import asyncio
import logging
from datetime import datetime, timezone
from celery import Task
from app.worker.celery_app import celery_app
from app.db.database import SessionLocal
from app.core.cache import cache

logger = logging.getLogger(__name__)


def _broadcast_task_completed(result: dict) -> None:
    """
    Broadcast task completion to WebSocket clients connected to THIS process.
    In a multi-process deployment a Redis pub/sub bridge would relay this to
    the API process — a WS broadcast failure must never affect the task result.
    """
    from app.core.connection_manager import manager

    notification = {
        "type": "task_completed",
        "payload": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.broadcast(notification))
        loop.close()
    except Exception:  # noqa: BLE001 — never fail the task over a notification
        logger.debug("WebSocket broadcast skipped (no clients in this process)")


class DatabaseTask(Task):
    """
    Base task class that manages a DB session.
    Tasks run in a separate process from FastAPI, so they need
    their own DB connections — they can't use FastAPI's get_db().
    This base class handles session lifecycle cleanly.
    """
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, *args, **kwargs):
        """Called after task finishes — close the DB session."""
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.worker.tasks.process_bulk_emissions",
    max_retries=3,
    default_retry_delay=30,  # seconds between retries
)
def process_bulk_emissions(self, company_id: int, records: list[dict]) -> dict:
    """
    Process a bulk emission upload in the background.

    `bind=True` means `self` is the task instance — gives us access
    to retry logic, task ID, and the DB session from DatabaseTask.

    This task:
    1. Validates each record
    2. Inserts into DB in a single transaction
    3. Invalidates the cache for this company
    4. Returns a summary of what was processed
    """
    from app.models.emission import EmissionRecord

    logger.info(
        f"[Task {self.request.id}] Processing {len(records)} "
        f"emission records for company {company_id}"
    )

    created = 0
    errors = []

    try:
        for i, record_data in enumerate(records):
            try:
                record = EmissionRecord(
                    company_id=company_id,
                    **record_data,
                )
                self.db.add(record)
                created += 1
            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        # Commit all valid records in one transaction
        # If this fails, we retry the whole task (see max_retries above)
        self.db.commit()

        # Invalidate all cached summaries for this company
        # — the data has changed so caches are now stale
        invalidated = cache.delete_pattern(f"summary:company:{company_id}:*")
        logger.info(
            f"[Task {self.request.id}] Invalidated {invalidated} cache keys"
        )

        result = {
            "status": "completed",
            "company_id": company_id,
            "records_created": created,
            "errors": errors,
            "task_id": self.request.id,
        }
        _broadcast_task_completed(result)
        return result

    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Failed: {exc}")
        # Celery retry — waits default_retry_delay seconds then tries again
        # exc=exc preserves the original exception in logs
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="app.worker.tasks.generate_csrd_report",
    max_retries=2,
    default_retry_delay=60,
)
def generate_csrd_report(self, company_id: int, year: int) -> dict:
    """
    Generate a full CSRD ESRS E1 report via the RAG pipeline (Phase 7).

    1. Pulls emission data + company info from the DB
    2. Retrieves regulatory context from the FAISS vector store
    3. Generates the narrative with the LLM
    4. Caches the result in Redis (csrd_report:{company_id}:{year}, TTL 1h)
    5. Notifies WebSocket clients (Phase 9)
    """
    from app.ml.csrd_report_generator import report_generator

    logger.info(
        f"[Task {self.request.id}] Generating CSRD report "
        f"for company {company_id}, year {year}"
    )

    try:
        report_text = report_generator.generate_report_sync(
            company_id=company_id,
            year=year,
            db=self.db,
        )

        cache.set(
            f"csrd_report:{company_id}:{year}",
            {"report": report_text, "generated_at": datetime.now(timezone.utc).isoformat()},
            ttl=3600,
        )

        result = {
            "status": "completed",
            "company_id": company_id,
            "year": year,
            "report": report_text,
            "word_count": len(report_text.split()),
            "task_id": self.request.id,
        }
        _broadcast_task_completed(result)
        return result

    except RuntimeError as exc:
        # LLM not configured — retrying won't help, fail immediately
        logger.error(f"[Task {self.request.id}] {exc}")
        return {
            "status": "failed",
            "company_id": company_id,
            "year": year,
            "error": str(exc),
            "task_id": self.request.id,
        }
    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Report generation failed: {exc}")
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.retrain_models",
    max_retries=1,
    default_retry_delay=300,
)
def retrain_models(self) -> dict:
    """
    Retrain the forecasting model and anomaly detector on current data.
    Runs the same pipeline as scripts/train_models.py, then clears the
    inference service's in-memory model cache.
    """
    logger.info(f"[Task {self.request.id}] Retraining ML models")

    db = SessionLocal()
    try:
        from app.core.config import settings
        from app.ml.anomaly_detector import train_anomaly_detector
        from app.ml.feature_engineering import (
            engineer_forecasting_features,
            load_emission_dataframe,
            prepare_features_and_target,
        )
        from app.ml.forecasting_model import train_with_mlflow
        from app.ml.model_registry import save_model

        df_raw = load_emission_dataframe(db)
        if df_raw.empty:
            return {
                "status": "failed",
                "error": "No emission data available for training",
                "task_id": self.request.id,
            }

        # ── Forecasting model ────────────────────────────────────────────
        df_features = engineer_forecasting_features(df_raw)
        X, y = prepare_features_and_target(df_features)
        forecasting_model, metrics, run_id = train_with_mlflow(X, y)

        forecasting_saved = False
        if metrics["val_r2"] >= settings.MIN_FORECAST_R2:
            save_model(
                forecasting_model,
                "forecasting",
                metadata={
                    "mlflow_run_id": run_id,
                    "val_r2": metrics["val_r2"],
                    "val_mae": metrics["val_mae"],
                },
            )
            forecasting_saved = True
        else:
            logger.error(
                f"Quality gate FAILED: R²={metrics['val_r2']:.3f} < "
                f"{settings.MIN_FORECAST_R2} — keeping previous model"
            )

        # ── Anomaly detector ─────────────────────────────────────────────
        anomaly_model, scaler, anomaly_run_id = train_anomaly_detector(df_raw)
        save_model(
            {"model": anomaly_model, "scaler": scaler},
            "anomaly_detector",
            metadata={"mlflow_run_id": anomaly_run_id},
        )

        # Clear the inference cache in THIS process; API replicas reload
        # from the 'latest' pointer files on their next model access
        from app.ml.inference import inference_service
        inference_service.reload_models()

        result = {
            "status": "completed",
            "forecasting_saved": forecasting_saved,
            "forecasting_r2": round(metrics["val_r2"], 4),
            "forecasting_mae": round(metrics["val_mae"], 2),
            "anomaly_detector_saved": True,
            "task_id": self.request.id,
        }
        _broadcast_task_completed(result)
        return result

    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Retraining failed: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()