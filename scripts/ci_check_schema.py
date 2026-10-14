import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.company import Company, IndustrySector
from app.models.emission import EmissionCategory, EmissionRecord, EmissionScope

engine = create_engine(os.environ["DATABASE_URL"])

with engine.connect() as conn:
    labels = [r[0] for r in conn.execute(text("SELECT unnest(enum_range(NULL::emissioncategory))::text"))]
    assert any(label.lower() == "fuel_energy_related" for label in labels), labels
    tables = {r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))}
    for table in ("companies", "emission_records", "emission_factors", "emission_factor_components", "users"):
        assert table in tables, f"missing table {table}: {sorted(tables)}"
    columns = {r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'emission_records'"))}
    for column in ("activity_group_id", "factor_post_type", "activity_label", "emission_factor_id", "calc_method"):
        assert column in columns, f"missing column {column}"

# The new enum value must be usable by the ORM, not just present in the type.
with Session(engine) as db:
    company = Company(name="CI check", sector=IndustrySector.OTHER, country="France")
    db.add(company)
    db.flush()
    db.add(EmissionRecord(
        company_id=company.id, scope=EmissionScope.SCOPE_3, category=EmissionCategory.FUEL_ENERGY_RELATED,
        co2_tonnes=1.0, reporting_year=2024, reporting_month=1,
    ))
    db.flush()
    db.rollback()

print("schema ok:", sorted(labels))
