import enum
from sqlalchemy import (
    Column, Integer, Float, String, Enum,
    ForeignKey, Text, CheckConstraint
)
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin


class EmissionScope(str, enum.Enum):
    """
    The GHG Protocol (which CSRD is built on) defines three scopes:
    - Scope 1: Direct emissions (company's own combustion, vehicles)
    - Scope 2: Indirect from purchased electricity/heat
    - Scope 3: All other indirect (supply chain, travel, waste)
    Scope 3 is typically 70-90% of a company's total footprint.
    """
    SCOPE_1 = "scope_1"
    SCOPE_2 = "scope_2"
    SCOPE_3 = "scope_3"


class EmissionCategory(str, enum.Enum):
    STATIONARY_COMBUSTION = "stationary_combustion"   # Scope 1: boilers, furnaces
    MOBILE_COMBUSTION = "mobile_combustion"            # Scope 1: company vehicles
    PURCHASED_ELECTRICITY = "purchased_electricity"   # Scope 2
    PURCHASED_HEAT = "purchased_heat"                 # Scope 2
    BUSINESS_TRAVEL = "business_travel"               # Scope 3
    EMPLOYEE_COMMUTING = "employee_commuting"         # Scope 3
    SUPPLY_CHAIN = "supply_chain"                     # Scope 3
    WASTE = "waste"                                   # Scope 3


class EmissionRecord(TimestampMixin, Base):
    __tablename__ = "emission_records"

    # Table-level constraints: catches bad data even if Python code has a bug
    __table_args__ = (
        CheckConstraint("co2_tonnes >= 0", name="check_co2_positive"),
        CheckConstraint("reporting_year >= 2000", name="check_year_valid"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key links this record to a company row
    # ondelete="CASCADE" means: if the company is deleted,
    # all its emission records are automatically deleted too.
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scope = Column(Enum(EmissionScope), nullable=False)
    category = Column(Enum(EmissionCategory), nullable=False)

    # Core measurement — always stored in tonnes CO2 equivalent
    # CO2e (CO2 equivalent) is the standard unit — it normalises
    # different greenhouse gases (methane, N2O etc.) to CO2 impact.
    co2_tonnes = Column(Float, nullable=False)

    reporting_year = Column(Integer, nullable=False)
    reporting_month = Column(Integer, nullable=True)  # None = full-year record

    # Data source tracking — auditors need this for CSRD compliance
    data_source = Column(String(255), nullable=True)  # "ERP export", "utility bill", "estimate"
    notes = Column(Text, nullable=True)

    # SQLAlchemy relationship — lets us do record.company to get the Company object
    # back_populates means Company will also have a .emission_records attribute
    company = relationship("Company", back_populates="emission_records")

    def __repr__(self):
        return (
            f"<EmissionRecord company_id={self.company_id} "
            f"scope={self.scope} year={self.reporting_year} "
            f"co2={self.co2_tonnes}t>"
        )