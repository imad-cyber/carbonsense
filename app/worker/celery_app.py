from celery import Celery
from app.core.config import settings

# create the first celery application

celery_app = Celery(
    "carbonsense",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include = [
        "app.worker.tasks", # tells Celery where to find task functions
    ]
)

celery_app.conf.update(
    task_serializer = "json",
    result_serializer = "json",
    accept_content = ["json"],

    result_expires = 3600,
    
    timezone = "Europe/Paris",
    enable_utc = True,
    
    task_routes={
        "app.worker.tasks.process_bulk_emissions": {"queue": "data"},
        "app.worker.tasks.generate_csrd_report": {"queue": "reports"},
        "app.worker.tasks.retrain_models": {"queue": "data"},
    },
    
)