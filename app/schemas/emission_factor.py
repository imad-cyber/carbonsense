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
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class EmissionFactorListResponse(BaseModel):
    items: list[EmissionFactorResponse]
    total: int
    page: int
    page_size: int
