import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.models.emission import EmissionRecord
from app.models.emission_factor import EmissionFactor
from app.schemas.emission import ActivityEmissionCreate
from app.services.allocation import AllocationPlan, plan_allocation
from app.services.calculation import Calculation, calculate_emissions
from app.services.company_service import CompanyService
from app.services.emission_factor_service import EmissionFactorService


@dataclass
class ComputedActivity:
    factor: EmissionFactor
    plan: AllocationPlan
    calculations: list[Calculation]


@dataclass
class ActivityResult:
    group_id: str
    records: list[EmissionRecord]
    calculations: list[Calculation]
    factor: EmissionFactor
    plan: AllocationPlan


class ActivityEmissionService:
    @staticmethod
    def compute(db: Session, data: ActivityEmissionCreate) -> ComputedActivity:
        """Everything except saving: factor lookup, allocation to scopes, calculation."""
        CompanyService.get_by_id(db, data.company_id)  # 404 if missing
        factor = EmissionFactorService.get_by_id(db, data.emission_factor_id)
        try:
            plan = plan_allocation(
                data.scope, data.category, factor.kg_co2e_per_unit, factor.components
            )
            calcs = [
                calculate_emissions(
                    quantity=data.quantity,
                    activity_unit=data.unit,
                    factor_kg_co2e_per_unit=s.kg_co2e_per_unit,
                    factor_unit=factor.unit,
                    uncertainty_pct=factor.uncertainty_pct,
                )
                for s in plan.slices
            ]
        except ValueError as exc:  # AllocationError, UnitMismatchError, bad quantities
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            )
        return ComputedActivity(factor, plan, calcs)

    @staticmethod
    def create(db: Session, data: ActivityEmissionCreate) -> ActivityResult:
        computed = ActivityEmissionService.compute(db, data)
        factor = computed.factor
        group_id = str(uuid.uuid4())
        records = [
            EmissionRecord(
                company_id=data.company_id,
                scope=s.scope,
                category=s.category,
                co2_tonnes=c.co2_tonnes,
                reporting_year=data.reporting_year,
                reporting_month=data.reporting_month,
                data_source=data.data_source,
                notes=data.notes,
                calc_method="activity_x_factor",
                activity_quantity=data.quantity,
                activity_unit=data.unit,
                emission_factor_id=factor.id,
                factor_kg_co2e_per_unit=s.kg_co2e_per_unit,
                factor_unit=factor.unit,
                factor_source_version=factor.source_version,
                factor_uncertainty_pct=factor.uncertainty_pct,
                activity_group_id=group_id,
                factor_post_type=s.post_type,
                activity_label=data.activity_label,
            )
            for s, c in zip(computed.plan.slices, computed.calculations)
        ]
        db.add_all(records)
        db.commit()
        for record in records:
            db.refresh(record)
        cache.delete_pattern(f"summary:company:{data.company_id}:*")
        return ActivityResult(group_id, records, computed.calculations, factor, computed.plan)
