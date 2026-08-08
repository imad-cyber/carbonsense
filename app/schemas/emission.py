from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime
from app.models.emission import EmissionScope, EmissionCategory


class EmissionRecordBase(BaseModel):
    scope: EmissionScope
    category: EmissionCategory
    co2_tonnes: float = Field(
        ...,
        gt=0,
        description="CO2 equivalent in metric tonnes",
        examples=[125.5],
    )
    reporting_year: int = Field(
        ...,
        ge=2000,
        le=2100,
        examples=[2024],
    )
    reporting_month: Optional[int] = Field(
        None,
        ge=1,
        le=12,
        description="Leave null for annual records",
    )
    data_source: Optional[str] = Field(
        None,
        max_length=255,
        examples=["ERP export Q4 2024"],
    )
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_scope_category_match(self) -> "EmissionRecordBase":
        """
        Business rule validation — some categories only make sense
        for certain scopes. This is domain logic, not just type checking.
        A model_validator runs after all individual field validators.
        """
        scope_1_categories = {
            EmissionCategory.STATIONARY_COMBUSTION,
            EmissionCategory.MOBILE_COMBUSTION,
        }
        scope_2_categories = {
            EmissionCategory.PURCHASED_ELECTRICITY,
            EmissionCategory.PURCHASED_HEAT,
        }
        scope_3_categories = {
            EmissionCategory.BUSINESS_TRAVEL,
            EmissionCategory.EMPLOYEE_COMMUTING,
            EmissionCategory.SUPPLY_CHAIN,
            EmissionCategory.WASTE,
        }

        if self.scope == EmissionScope.SCOPE_1 and self.category not in scope_1_categories:
            raise ValueError(f"Category {self.category} is not valid for Scope 1")
        if self.scope == EmissionScope.SCOPE_2 and self.category not in scope_2_categories:
            raise ValueError(f"Category {self.category} is not valid for Scope 2")
        if self.scope == EmissionScope.SCOPE_3 and self.category not in scope_3_categories:
            raise ValueError(f"Category {self.category} is not valid for Scope 3")

        return self


class EmissionRecordCreate(EmissionRecordBase):
    company_id: int = Field(..., gt=0)


class EmissionRecordUpdate(BaseModel):
    co2_tonnes: Optional[float] = Field(None, gt=0)
    reporting_year: Optional[int] = Field(None, ge=2000, le=2100)
    reporting_month: Optional[int] = Field(None, ge=1, le=12)
    data_source: Optional[str] = None
    notes: Optional[str] = None


class EmissionRecordResponse(EmissionRecordBase):
    id: int
    company_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmissionSummary(BaseModel):
    """
    Aggregated view — used by the dashboard and ML pipeline.
    Shows totals broken down by scope for a company/year.
    """
    company_id: int
    reporting_year: int
    scope_1_total: float
    scope_2_total: float
    scope_3_total: float
    grand_total: float
    record_count: int

class BulkEmissionUpload(BaseModel):
    """
    Schema for bulk emission upload.
    company_id comes from the URL path, not the body —
    records are a list of emission data without company_id
    (we'll attach it in the endpoint).
    """
    records: list[EmissionRecordBase] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of emission records — max 500 per request",
    )


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str