"""
CarbonSense Weekly Retraining DAG

Schedule: every Sunday at 03:00 Europe/Paris
Single task: trigger the Celery retrain_models task and log the task_id.
"""
import logging
import sys
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, "/opt/airflow")

logger = logging.getLogger(__name__)

PARIS_TZ = pendulum.timezone("Europe/Paris")


def trigger_retraining(**_):
    """Queue the Celery retraining task — the worker does the heavy lifting."""
    from app.worker.tasks import retrain_models

    task = retrain_models.delay()
    logger.info(f"Weekly retraining queued — Celery task_id={task.id}")
    return task.id


with DAG(
    dag_id="carbonsense_weekly_retraining",
    description="Weekly ML model retraining trigger",
    schedule="0 3 * * 0",
    start_date=pendulum.datetime(2025, 1, 1, tz=PARIS_TZ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "carbonsense",
        "retries": 1,
        "retry_delay": timedelta(minutes=10),
    },
    tags=["carbonsense", "ml", "weekly"],
) as dag:
    PythonOperator(
        task_id="trigger_celery_retraining",
        python_callable=trigger_retraining,
    )
