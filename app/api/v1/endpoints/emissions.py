from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.database import get_db
from app.schemas.emission import (
    EmissionRecordCreate,
    EmissionRecordUpdate,
    EmissionRecordResponse,
    EmissionSummary,
)
from app.models.emission import EmissionScope
from app.services.emission_service import EmissionService
from app.core.dependencies import (
    require_any_authenticated,
    require_analyst_or_above,
    require_admin,
)
from app.models.user import User
from app.worker.tasks import process_bulk_emissions, generate_csrd_report
from app.schemas.emission import BulkEmissionUpload, TaskStatusResponse


router = APIRouter(prefix="/emissions", tags=["Emissions"])


@router.get("/company/{company_id}", response_model=dict)
def list_company_emissions(
    company_id: int,
    year: Optional[int] = Query(None, ge=2000, le=2100),
    scope: Optional[EmissionScope] = Query(None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated)
):
    items, total = EmissionService.get_by_company(
        db, company_id, year, scope, page, page_size
    )
    return {
        "items": [EmissionRecordResponse.model_validate(i) for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/", response_model=EmissionRecordResponse, status_code=status.HTTP_201_CREATED)
def create_emission_record(
    payload: EmissionRecordCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above)
):
    return EmissionService.create(db, payload)


@router.get("/{record_id}", response_model=EmissionRecordResponse)
def get_emission_record(record_id: int, db: Session = Depends(get_db), _: User = Depends(require_any_authenticated)):
    return EmissionService.get_by_id(db, record_id)


@router.patch("/{record_id}", response_model=EmissionRecordResponse)
def update_emission_record(
    record_id: int,
    payload: EmissionRecordUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above)
):
    return EmissionService.update(db, record_id, payload)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_emission_record(record_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    EmissionService.delete(db, record_id)


@router.get("/summary/{company_id}/{year}", response_model=EmissionSummary)
def get_emission_summary(company_id: int, year: int, db: Session = Depends(get_db), _: User = Depends(require_any_authenticated)):
    """
    Aggregated Scope 1/2/3 totals for a company in a given year.
    This endpoint feeds the frontend dashboard and the ML pipeline.
    """
    return EmissionService.get_summary(db, company_id, year)


@router.post(
    "/bulk/{company_id}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    # 202 Accepted = "I received this, processing has started,
    # come back later for the result"
)
def bulk_upload_emissions(
    company_id: int,
    payload: BulkEmissionUpload,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """
    Asynchronous bulk upload — returns immediately with a task ID.
    Client polls GET /tasks/{task_id} to check progress.
    This pattern is called 'async task with polling' and is standard
    for long-running operations in enterprise APIs.
    """
    # Verify company exists before queuing the task
    from app.services.company_service import CompanyService
    CompanyService.get_by_id(db, company_id)

    # Serialise records to plain dicts — Celery needs JSON-serialisable data
    records_data = [r.model_dump() for r in payload.records]

    # .delay() queues the task and returns immediately
    # The actual work happens in the Celery worker process
    task = process_bulk_emissions.delay(company_id, records_data)

    return TaskStatusResponse(
        task_id=task.id,
        status="queued",
        message=f"{len(records_data)} records queued for processing. "
                f"Poll /api/v1/tasks/{task.id} for status.",
    )


@router.post(
    "/report/{company_id}/{year}",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_csrd_report(
    company_id: int,
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """Trigger async CSRD report generation. Will be fully implemented in Phase 7."""
    from app.services.company_service import CompanyService
    CompanyService.get_by_id(db, company_id)

    task = generate_csrd_report.delay(company_id, year)

    return TaskStatusResponse(
        task_id=task.id,
        status="queued",
        message=f"CSRD report generation started for company {company_id}, year {year}.",
    )