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
from app.services.factor_checks import factor_warnings

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
    source_label = (
        "ADEME Base Carbone (Licence Ouverte 2.0)"
        if factor.source == "ADEME_BASE_CARBONE" else factor.source
    )
    where = f" ({factor.sub_geography})" if factor.sub_geography else ""
    return ActivityEmissionResult(
        record=record,
        calculation=CalculationBreakdown(
            formula=formula,
            co2_tonnes=calc.co2_tonnes,
            co2_tonnes_low=None if calc.co2_tonnes_low is None else round(calc.co2_tonnes_low, 6),
            co2_tonnes_high=None if calc.co2_tonnes_high is None else round(calc.co2_tonnes_high, 6),
            note=(
                f"Factor {factor.source_id}: {factor.name}{where}. Source: {source_label}, "
                f"version {factor.source_version}. The range reflects the factor's stated "
                "uncertainty only, not errors in the activity data."
            ),
            warnings=factor_warnings(
                status=factor.status,
                valid_until=factor.valid_until,
                uncertainty_pct=factor.uncertainty_pct,
                reporting_year=payload.reporting_year,
            ),
        ),
    )
