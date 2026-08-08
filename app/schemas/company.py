from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from app.models.company import IndustrySector


class CompanyBase(BaseModel):
    """
    Shared fields used by both Create and Update schemas.
    This avoids repeating field definitions.
    Field() lets us add metadata: description shows in Swagger docs,
    examples make the docs interactive and useful.
    """
    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Legal company name",
        examples=["TotalEnergies SE"],
    )
    sector: IndustrySector = Field(
        ...,
        description="Industry sector for emission factor selection",
        examples=["energy"],
    )
    country: str = Field(
        default="France",
        max_length=100,
        examples=["France"],
    )
    description: Optional[str] = Field(None, max_length=2000)
    employee_count: Optional[int] = Field(None, gt=0)
    annual_revenue_eur: Optional[int] = Field(
        None,
        gt=0,
        description="Annual revenue in thousands of euros",
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        """
        Validators run on every field before the object is created.
        This catches edge cases Pydantic's built-in checks miss.
        """
        if not v.strip():
            raise ValueError("Company name cannot be blank or whitespace")
        return v.strip()


class CompanyCreate(CompanyBase):
    """
    Schema for POST /companies requests.
    Inherits all fields from CompanyBase.
    Currently adds nothing extra — but having a separate class
    means we can add create-only fields later without breaking anything.
    """
    pass


class CompanyUpdate(BaseModel):
    """
    Schema for PATCH /companies/{id} — all fields are optional.
    PATCH means "update only what I send". Different from PUT
    which replaces the entire resource.
    """
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    sector: Optional[IndustrySector] = None
    country: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    employee_count: Optional[int] = Field(None, gt=0)
    annual_revenue_eur: Optional[int] = Field(None, gt=0)


class CompanyResponse(CompanyBase):
    """
    Schema for responses — what the API sends back.
    Adds DB-generated fields: id, timestamps.
    model_config tells Pydantic to read values from ORM objects
    (SQLAlchemy models), not just dicts.
    """
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    """
    Paginated list response — always wrap lists in an object.
    This lets you add total_count, page, etc. without breaking
    existing clients. Direct arrays are a versioning nightmare.
    """
    items: list[CompanyResponse]
    total: int
    page: int
    page_size: int