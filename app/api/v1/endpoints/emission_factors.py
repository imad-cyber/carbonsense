from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.dependencies import require_any_authenticated
from app.db.database import get_db
from app.models.user import User
from app.schemas.emission_factor import EmissionFactorListResponse, EmissionFactorResponse
from app.services.emission_factor_service import EmissionFactorService

router = APIRouter(prefix="/emission-factors", tags=["Emission Factors"])


@router.get("/", response_model=EmissionFactorListResponse)
def search_emission_factors(
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Search in the factor name"),
    unit: Optional[str] = Query(None, max_length=50),
    geography: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """Search official emission factors. Every factor carries its source and version."""
    items, total = EmissionFactorService.search(db, q, unit, geography, page, page_size)
    return EmissionFactorListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{factor_id}", response_model=EmissionFactorResponse)
def get_emission_factor(
    factor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    return EmissionFactorService.get_by_id(db, factor_id)
