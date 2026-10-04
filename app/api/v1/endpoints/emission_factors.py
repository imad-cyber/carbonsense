from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import require_any_authenticated
from app.db.database import get_db
from app.models.user import User
from app.schemas.emission_factor import (
    EmissionFactorDetail,
    EmissionFactorListResponse,
    EmissionFactorResponse,
)
from app.services.emission_factor_service import EmissionFactorService

router = APIRouter(prefix="/emission-factors", tags=["Emission Factors"])


@router.get("/", response_model=EmissionFactorListResponse)
def search_emission_factors(
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Search in the factor name"),
    unit: Optional[str] = Query(None, max_length=50),
    geography: Optional[str] = Query(None, max_length=100),
    category: Optional[str] = Query(None, max_length=100, description="Search in the category path"),
    include_archived: bool = Query(False, description="Archived factors are hidden by default"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """Search official emission factors. Every factor carries its source and version."""
    items, total = EmissionFactorService.search(
        db, q, unit, geography, category, include_archived, page, page_size
    )
    return EmissionFactorListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{factor_id}", response_model=EmissionFactorDetail)
def get_emission_factor(
    factor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """One factor with its components (e.g. Combustion vs Amont) when the source provides them."""
    factor = EmissionFactorService.get_by_id(db, factor_id)
    return EmissionFactorDetail.model_validate(factor)  # inside the request, session still open
