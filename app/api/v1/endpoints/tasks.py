from fastapi import APIRouter, Depends
from app.worker.celery_app import celery_app
from app.core.dependencies import require_any_authenticated
from app.models.user import User

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}")
def get_task_status(
    task_id: str,
    _: User = Depends(require_any_authenticated),
):
    """
    Poll this endpoint to check background task progress.

    Celery task states:
    - PENDING  → queued, not started yet
    - STARTED  → worker picked it up, running now
    - SUCCESS  → finished, result is available
    - FAILURE  → something went wrong, error is in result
    - RETRY    → failed, waiting to retry
    """
    result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
    }

    if result.successful():
        response["result"] = result.get()
    elif result.failed():
        response["error"] = str(result.result)

    return response