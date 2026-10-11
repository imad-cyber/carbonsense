from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_analyst_or_above, require_any_authenticated
from app.db.database import get_db
from app.models.user import User
from app.schemas.emission import (
    ActivityEmissionCreate,
    ActivityEmissionResult,
    CalculationBreakdown,
    SliceBreakdown,
)
from app.services.activity_emission_service import ActivityEmissionService
from app.services.factor_checks import factor_warnings

router = APIRouter(prefix="/emissions", tags=["Emissions"])


def _r(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _breakdown(payload, factor, plan, calcs) -> CalculationBreakdown:
    slices = [
        SliceBreakdown(
            scope=s.scope,
            category=s.category,
            post_type=s.post_type,
            kg_co2e_per_unit=s.kg_co2e_per_unit,
            co2_tonnes=c.co2_tonnes,
            co2_tonnes_low=_r(c.co2_tonnes_low),
            co2_tonnes_high=_r(c.co2_tonnes_high),
        )
        for s, c in zip(plan.slices, calcs)
    ]
    source_label = (
        "ADEME Base Carbone (Licence Ouverte 2.0)"
        if factor.source == "ADEME_BASE_CARBONE" else factor.source
    )
    where = f" ({factor.sub_geography})" if factor.sub_geography else ""
    return CalculationBreakdown(
        formula=f"{payload.quantity:g} {payload.unit} = {calcs[0].quantity_in_factor_unit:g} {factor.unit}",
        co2_tonnes_total=round(sum(c.co2_tonnes for c in calcs), 6),
        slices=slices,
        note=(
            f"Factor {factor.source_id}: {factor.name}{where}. Source: {source_label}, "
            f"version {factor.source_version}. Posts are booked to scopes under "
            "CarbonSense's allocation policy (docs/METHODOLOGY.md). The ranges reflect the "
            "factor's stated uncertainty only, not errors in the activity data."
        ),
        warnings=plan.warnings + factor_warnings(
            status=factor.status,
            valid_until=factor.valid_until,
            uncertainty_pct=factor.uncertainty_pct,
            reporting_year=payload.reporting_year,
            reporting_month=payload.reporting_month,
        ),
    )


@router.post("/from-activity/preview", response_model=CalculationBreakdown)
def preview_emission_from_activity(
    payload: ActivityEmissionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """Same calculation as /from-activity, but nothing is saved. Open to read-only users."""
    computed = ActivityEmissionService.compute(db, payload)
    return _breakdown(payload, computed.factor, computed.plan, computed.calculations)


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
    Calculate emissions as activity quantity x emission factor and save them.
    For fuel and electricity factors the factor's posts are booked to their scopes
    (e.g. combustion -> Scope 1, upstream -> Scope 3), so one input can create several
    records sharing an activity_group_id.
    """
    result = ActivityEmissionService.create(db, payload)
    return ActivityEmissionResult(
        activity_group_id=result.group_id,
        records=result.records,
        calculation=_breakdown(payload, result.factor, result.plan, result.calculations),
    )
