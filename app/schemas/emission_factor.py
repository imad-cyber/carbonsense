from datetime import date
from typing import Optional
from pydantic import BaseModel


class EmissionFactorResponse(BaseModel):
    id: int
    source: str
    source_id: str
    source_version: str
    name: str
    unit: str
    kg_co2e_per_unit: float
    uncertainty_pct: Optional[float] = None
    geography: Optional[str] = None
    sub_geography: Optional[str] = None
    status: Optional[str] = None
    category_path: Optional[str] = None
    valid_until: Optional[date] = None

    model_config = {"from_attributes": True}


class FactorComponentResponse(BaseModel):
    post_type: str
    post_name: Optional[str] = None
    kg_co2e_per_unit: float
    gases: Optional[dict[str, float]] = None

    model_config = {"from_attributes": True}


class EmissionFactorDetail(EmissionFactorResponse):
    components: list[FactorComponentResponse] = []


class EmissionFactorListResponse(BaseModel):
    items: list[EmissionFactorResponse]
    total: int
    page: int
    page_size: int
