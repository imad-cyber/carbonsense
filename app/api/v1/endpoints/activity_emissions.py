from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.dependencies import require_analyst_or_above
from app.db.database import get_db
from app.models.user import User
from app.schemas.emission import (
    ActivityEmissionCreate,
    ActivityEmissionResult,
    CalculationBreakdown,
)
from app.services.activity_emission_service import ActivityEmissionService

router = APIRouter(prefix="/emissions", tags=["Emissions"])


@router.post(
    "/from-activity",
    response_model=ActivityEmissionResult,
    status_code=status.HTTP_201_CREATED,
)
def create_emission_from_activity(
    payload: ActivityEmissionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """
    Calculate emissions as activity quantity x emission factor.
    The factor value and version are stored on the record so the figure
    stays reproducible even if the factor is later updated.
    """
    record, calc, factor = ActivityEmissionService.create(db, payload)
    formula = (
        f"{payload.quantity:g} {payload.unit} -> {calc.quantity_in_factor_unit:g} {factor.unit}"
        f" x {factor.kg_co2e_per_unit:g} kg CO2e/{factor.unit}"
        f" = {calc.co2_tonnes:.6g} t CO2e"
    )
    return ActivityEmissionResult(
        record=record,
        calculation=CalculationBreakdown(
            formula=formula,
            co2_tonnes=calc.co2_tonnes,
            co2_tonnes_low=calc.co2_tonnes_low,
            co2_tonnes_high=calc.co2_tonnes_high,
            note=(
                f"Source: {factor.source} {factor.source_version}. The range reflects "
                "the factor's stated uncertainty only, not errors in the activity data."
            ),
        ),
    )
