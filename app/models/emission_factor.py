from sqlalchemy import JSON, Column, Float, Integer, String, UniqueConstraint
from app.db.database import Base
from app.models.base import TimestampMixin


class EmissionFactor(TimestampMixin, Base):
    """One emission factor from an official source, versioned so results stay traceable."""
    __tablename__ = "emission_factors"
    __table_args__ = (
        UniqueConstraint("source", "source_id", "source_version", name="uq_emission_factor_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, index=True)    # e.g. "ADEME_BASE_CARBONE"
    source_id = Column(String(100), nullable=False)            # the source's own identifier
    source_version = Column(String(50), nullable=False)        # e.g. "V23.6" or an import date
    name = Column(String(500), nullable=False, index=True)
    unit = Column(String(50), nullable=False)                  # the factor is "kg CO2e per <unit>"
    kg_co2e_per_unit = Column(Float, nullable=False)
    uncertainty_pct = Column(Float, nullable=True)
    geography = Column(String(100), nullable=True)
    status = Column(String(50), nullable=True)
    raw = Column(JSON, nullable=True)                          # original row, for audit

    def __repr__(self):
        return f"<EmissionFactor {self.source}:{self.source_id} {self.kg_co2e_per_unit} kgCO2e/{self.unit}>"
