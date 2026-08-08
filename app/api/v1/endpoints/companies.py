from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.company import (
    CompanyCreate, CompanyUpdate,
    CompanyResponse, CompanyListResponse,
)
from app.services.company_service import CompanyService
from app.core.dependencies import (
    require_any_authenticated,
    require_analyst_or_above,
    require_admin,
)
from app.models.user import User

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/", response_model=CompanyListResponse)
def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    # Any logged-in user can list companies
    _: User = Depends(require_any_authenticated),
):
    items, total = CompanyService.get_all(db, page, page_size)
    return CompanyListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    # Only analysts and admins can create companies
    _: User = Depends(require_analyst_or_above),
):
    return CompanyService.create(db, payload)


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    return CompanyService.get_by_id(db, company_id)


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    return CompanyService.update(db, company_id, payload)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    # Only admins can delete companies — destructive operation
    _: User = Depends(require_admin),
):
    CompanyService.delete(db, company_id)