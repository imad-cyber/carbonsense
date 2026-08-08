"""
CarbonSense Daily Pipeline DAG

Schedule: daily at 02:00 Europe/Paris
Tasks (in order):
1. check_db_health       → test DB connection, fail fast if down
2. validate_recent_data  → run EmissionDataValidator on yesterday's records
3. compute_summaries     → recompute and cache emission summaries for active companies
4. detect_anomalies      → run anomaly detector on recent records, log count
5. refresh_vector_store  → re-ingest any new regulatory documents
6. trigger_model_check   → check if models are stale (> 7 days), queue retraining if so

Dependencies: 1 >> 2 >> 3 >> [4, 5] >> 6
"""
import logging
import sys
from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

# The app package is mounted alongside dags/ in the Airflow container
sys.path.insert(0, "/opt/airflow")

logger = logging.getLogger(__name__)

PARIS_TZ = pendulum.timezone("Europe/Paris")


def check_db_health(**_):
    """Fail fast if the application database is unreachable."""
    from sqlalchemy import text

    from app.db.database import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info("Database health check passed")


def validate_recent_data(**_):
    """Run data quality validation on records created in the last day."""
    from datetime import timezone

    from app.data_pipeline.data_validator import validator
    from app.db.database import SessionLocal
    from app.models.emission import EmissionRecord

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        records = (
            db.query(EmissionRecord)
            .filter(EmissionRecord.created_at >= cutoff)
            .all()
        )
        if not records:
            logger.info("No new records in the last 24h — nothing to validate")
            return

        payload = [
            {
                "scope": r.scope.value,
                "category": r.category.value,
                "co2_tonnes": r.co2_tonnes,
                "reporting_year": r.reporting_year,
                "reporting_month": r.reporting_month,
            }
            for r in records
        ]
        report = validator.validate_batch(payload)
        logger.info(
            f"Validation: {report['passed']}/{report['total']} passed, "
            f"{report['failed']} failed, {report['warnings']} warnings"
        )
        if report["failed"] > 0:
            for bad in report["invalid_records"]:
                logger.warning(f"Invalid record: {bad['reasons']}")
    finally:
        db.close()


def compute_summaries(**_):
    """Recompute and cache the current-year summary for every company."""
    from app.db.database import SessionLocal
    from app.models.company import Company
    from app.services.emission_service import EmissionService

    db = SessionLocal()
    try:
        year = datetime.now().year
        companies = db.query(Company).all()
        for company in companies:
            try:
                summary = EmissionService.get_summary(db, company.id, year)
                logger.info(
                    f"Summary cached — company {company.id}: "
                    f"{summary.grand_total:,.1f}t CO2e"
                )
            except Exception as e:  # a single company must not fail the run
                logger.warning(f"Summary failed for company {company.id}: {e}")
    finally:
        db.close()


def detect_anomalies(**_):
    """Score current-year records for every company, log anomaly counts."""
    from app.db.database import SessionLocal
    from app.ml.inference import inference_service
    from app.ml.model_registry import model_exists
    from app.models.company import Company

    if not model_exists("anomaly_detector"):
        logger.warning("Anomaly detector not trained — skipping")
        return

    db = SessionLocal()
    try:
        year = datetime.now().year
        total_anomalies = 0
        for company in db.query(Company).all():
            try:
                result = inference_service.detect_anomalies(db, company.id, year)
                total_anomalies += result["anomaly_count"]
            except Exception as e:
                logger.debug(f"Anomaly scan skipped for company {company.id}: {e}")
        logger.info(f"Daily anomaly scan complete — {total_anomalies} anomalies flagged")
    finally:
        db.close()


def refresh_vector_store(**_):
    """Re-ingest regulatory documents into the FAISS store."""
    from app.core.config import settings
    from app.ml.vector_store_manager import vector_store_manager

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — skipping vector store refresh")
        return

    chunks = vector_store_manager.ingest_regulatory_text()
    logger.info(f"Vector store refreshed — {chunks} chunks ingested")


def trigger_model_check(**_):
    """Queue retraining if the forecasting model is older than 7 days."""
    from pathlib import Path

    from app.core.config import settings

    model_path = Path(settings.MODEL_DIR) / "forecasting_latest.joblib"
    if not model_path.exists():
        stale = True
        logger.warning("No forecasting model found — queuing initial training")
    else:
        age_days = (
            datetime.now() - datetime.fromtimestamp(model_path.stat().st_mtime)
        ).days
        stale = age_days > 7
        logger.info(f"Forecasting model age: {age_days} days (stale: {stale})")

    if stale:
        from app.worker.tasks import retrain_models

        task = retrain_models.delay()
        logger.info(f"Retraining queued — Celery task {task.id}")


def on_failure_callback(context):
    """Log pipeline failures — the record is queryable for alerting."""
    task_id = context.get("task_instance").task_id if context.get("task_instance") else "?"
    logger.error(f"CarbonSense pipeline task FAILED: {task_id} — {context.get('exception')}")


with DAG(
    dag_id="carbonsense_daily_pipeline",
    description="Daily data quality, caching, anomaly and model freshness pipeline",
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2025, 1, 1, tz=PARIS_TZ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "carbonsense",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_callback,
    },
    tags=["carbonsense", "daily"],
) as dag:
    t1 = PythonOperator(task_id="check_db_health", python_callable=check_db_health)
    t2 = PythonOperator(task_id="validate_recent_data", python_callable=validate_recent_data)
    t3 = PythonOperator(task_id="compute_summaries", python_callable=compute_summaries)
    t4 = PythonOperator(task_id="detect_anomalies", python_callable=detect_anomalies)
    t5 = PythonOperator(task_id="refresh_vector_store", python_callable=refresh_vector_store)
    t6 = PythonOperator(task_id="trigger_model_check", python_callable=trigger_model_check)

    t1 >> t2 >> t3 >> [t4, t5] >> t6
