import enum
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Enum, Text
from app.db.database import Base
from app.models.base import TimestampMixin

class IndustrySector(str, enum.Enum):
    """
    Using an Enum (not free-text strings) means only valid sectors
    can be stored. Bad data is rejected at the DB level, not just
    in Python. This is data integrity.
    """

    ENERGY = "energy"
    MANUFACTURING = "manufacturing"
    TRANSPORT = "transport"
    FINANCE = "finance"
    TECHNOLOGY = "technology"
    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    OTHER = "other"

class Company(TimestampMixin, Base):
    """
    __tablename__ tells SQLAlchemy what the actual table is called in PostgreSQL.
    Every column is defined as a class attribute with its type and constraints.
    """

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    sector = Column(Enum(IndustrySector), nullable=False)
    country = Column(String(100), nullable=False, default="France")
    description = Column(Text, nullable=True)
    employee_count = Column(Integer, nullable=True)
    annual_revenue_eur = Column(Integer, nullable=True)

    emission_records = relationship(
        "EmissionRecord",
        back_populates="company",
        cascade = "all, delete-orphan"
    )

    def __repr__(self):
        return f"<Company id = {self.id} name = {self.name}>"
    
