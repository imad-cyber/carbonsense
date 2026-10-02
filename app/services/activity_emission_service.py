from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.cache import cache
from app.models.emission import EmissionRecord
from app.models.emission_factor import EmissionFactor
from app.schemas.emission import ActivityEmissionCreate
from app.services.calculation import Calculation, calculate_emissions
from app.services.company_service import CompanyService
from app.services.emission_factor_service import EmissionFactorService


class ActivityEmissionService:
    @staticmethod
    def create(
        db: Session, data: ActivityEmissionCreate
    ) -> tuple[EmissionRecord, Calculation, EmissionFactor]:
        CompanyService.get_by_id(db, data.company_id)  # 404 if missing
        factor = EmissionFactorService.get_by_id(db, data.emission_factor_id)

        try:
            calc = calculate_emissions(
                quantity=data.quantity,
                activity_unit=data.unit,
                factor_kg_co2e_per_unit=factor.kg_co2e_per_unit,
                factor_unit=factor.unit,
                uncertainty_pct=factor.uncertainty_pct,
            )
        except ValueError as exc:  # includes UnitMismatchError
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            )

        record = EmissionRecord(
            company_id=data.company_id,
            scope=data.scope,
            category=data.category,
            co2_tonnes=calc.co2_tonnes,
            reporting_year=data.reporting_year,
            reporting_month=data.reporting_month,
            data_source=data.data_source,
            notes=data.notes,
            calc_method="activity_x_factor",
            activity_quantity=data.quantity,
            activity_unit=data.unit,
            emission_factor_id=factor.id,
            factor_kg_co2e_per_unit=factor.kg_co2e_per_unit,
            factor_unit=factor.unit,
            factor_source_version=factor.source_version,
            factor_uncertainty_pct=factor.uncertainty_pct,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        cache.delete_pattern(f"summary:company:{record.company_id}:*")
        return record, calc, factor
