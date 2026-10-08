"""
Seeds one clearly labelled DEMO company with 36 months of activity data (gas, road diesel,
electricity), calculated through the real pipeline with real ADEME factors.
Activity quantities are synthetic; the factors are not. Three anomalies are planted
(noted in the records) as an illustration, not a benchmark.

  python scripts/seed_demo_company.py --dry-run
  python scripts/seed_demo_company.py
  python scripts/seed_demo_company.py --reset
"""
import math
import os
import random
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi import HTTPException
from sqlalchemy import or_, text

from app.core.cache import cache
from app.db.database import SessionLocal
from app.ingest.ademe import SOURCE, norm
from app.models.company import Company, IndustrySector
from app.models.emission import EmissionCategory, EmissionRecord, EmissionScope
from app.models.emission_factor import EmissionFactor
from app.schemas.emission import ActivityEmissionCreate
from app.services.activity_emission_service import ActivityEmissionService
from app.services.allocation import plan_allocation
from app.services.calculation import calculate_emissions

COMPANY_NAME = "Démo Industrie SA (synthetic activity data)"
YEARS = (2022, 2023, 2024)
MIN_ELECTRICITY_FACTOR_YEAR = 2018
S1, S2 = EmissionScope.SCOPE_1, EmissionScope.SCOPE_2

STREAMS = [
    dict(key="gas", scope=S1, category=EmissionCategory.STATIONARY_COMBUSTION,
         unit="MWh PCS", base=450.0, amp=0.45, peak=1),
    dict(key="diesel", scope=S1, category=EmissionCategory.MOBILE_COMBUSTION,
         unit="litre", base=18_000.0, amp=0.05, peak=12),
    dict(key="electricity", scope=S2, category=EmissionCategory.PURCHASED_ELECTRICITY,
         unit="kWh", base=1_800_000.0, amp=0.10, peak=1),
]
PLANTED = {  # (year, month, stream) -> multiplier on the quantity
    (2022, 9, "diesel"): 2.0,
    (2023, 2, "gas"): 2.6,
    (2024, 6, "electricity"): 0.3,
}


def quantity(stream: dict, year: int, month: int, rng: random.Random) -> float:
    seasonal = 1 + stream["amp"] * math.cos(2 * math.pi * (month - stream["peak"]) / 12)
    decline = 0.97 ** (year - YEARS[0])  # 3% yearly reduction
    return stream["base"] * seasonal * decline * rng.gauss(1.0, 0.04)


def resolve_factors(db) -> tuple[dict, list[int]]:
    def by_source_id(source_id: str) -> EmissionFactor:
        f = (
            db.query(EmissionFactor)
            .filter(EmissionFactor.source == SOURCE, EmissionFactor.source_id == source_id)
            .order_by(EmissionFactor.source_version.desc())
            .first()
        )
        if f is None:
            sys.exit(f"ADEME factor {source_id} not found. Run import_ademe.py load first.")
        return f

    candidates = (
        db.query(EmissionFactor)
        .filter(
            EmissionFactor.source == SOURCE,
            EmissionFactor.geography == "France continentale",
            EmissionFactor.name.ilike("%mix moyen - consommation%"),
            or_(EmissionFactor.status.is_(None), ~EmissionFactor.status.ilike("archiv%")),
        )
        .all()
    )
    by_year = {}
    for f in candidates:
        m = re.fullmatch(r"electricite_(\d{4})_mix_moyen_consommation", norm(f.name))
        if m and f.unit.lower() == "kwh":
            by_year[int(m.group(1))] = f
    if not by_year:
        sys.exit("No France 'mix moyen - consommation' electricity factor found.")
    latest = max(by_year)
    if latest < MIN_ELECTRICITY_FACTOR_YEAR:
        sys.exit(f"Newest electricity factor is from {latest} (available: {sorted(by_year)}). "
                 "Not using it for 2022-2024 data; send me this message.")
    missing = [y for y in YEARS if y not in by_year]
    if missing:
        sys.exit(f"No France electricity factor for {missing} (available: {sorted(by_year)}).")
    return {
        "gas": by_source_id("37133"),      # Gaz naturel - 2022 - mix moyen - consommation (kWh PCS)
        "diesel": by_source_id("25775"),   # Gazole routier - B7 (litre)
        "electricity": by_year[latest],    # used only for the dry run's January 2024
    }, sorted(by_year), by_year


def describe(factors: dict, years: list[int]) -> None:
    print("Factors used:")
    for key, f in factors.items():
        print(f"  {key}: ademe id {f.source_id} | {f.name} | {f.kg_co2e_per_unit} kgCO2e/{f.unit} | "
              f"{f.status} | posts: {[c.post_type for c in f.components]}")
    print(f"  electricity years available: {years}")


def dry_run(factors: dict) -> None:
    rng = random.Random(42)
    print("\nJanuary 2024, one month of each stream (no database writes):")
    for s in STREAMS:
        f = factors[s["key"]]
        q = quantity(s, 2024, 1, rng)
        plan = plan_allocation(s["scope"], s["category"], f.kg_co2e_per_unit, f.components)
        print(f"  {s['key']}: {q:,.1f} {s['unit']}")
        for sl in plan.slices:
            c = calculate_emissions(q, s["unit"], sl.kg_co2e_per_unit, f.unit, f.uncertainty_pct)
            print(f"      {sl.scope.value} / {sl.category.value} / {sl.post_type}: {c.co2_tonnes:,.2f} t")
        for w in plan.warnings:
            print("      warning:", w)


def main() -> None:
    args = set(sys.argv[1:])
    db = SessionLocal()
    try:
        factors, years, elec_by_year = resolve_factors(db)
        describe(factors, years)
        if "--dry-run" in args:
            dry_run(factors)
            return

        company = db.query(Company).filter(Company.name == COMPANY_NAME).first()
        if company is None:
            company = Company(
                name=COMPANY_NAME, sector=IndustrySector.MANUFACTURING, country="France",
                description="Fictional company for demonstration. Activity quantities are "
                            "synthetic; emission factors are real (ADEME Base Carbone).",
                employee_count=2500, annual_revenue_eur=600_000,
            )
            db.add(company)
            db.commit()
            db.refresh(company)

        existing = db.query(EmissionRecord).filter(
            EmissionRecord.company_id == company.id,
            EmissionRecord.calc_method == "activity_x_factor",
        )
        if existing.count() and "--reset" not in args:
            sys.exit("Demo data already exists. Use --reset to regenerate it.")
        if existing.count():
            existing.delete(synchronize_session=False)
            db.commit()
            cache.delete_pattern(f"summary:company:{company.id}:*")

        rng = random.Random(42)
        for year in YEARS:
            for month in range(1, 13):
                for s in STREAMS:
                    q = quantity(s, year, month, rng)
                    mult = PLANTED.get((year, month, s["key"]))
                    if mult:
                        q *= mult
                    ActivityEmissionService.create(db, ActivityEmissionCreate(
                        company_id=company.id, scope=s["scope"], category=s["category"],
                                                emission_factor_id=(
                            elec_by_year[year] if s["key"] == "electricity" else factors[s["key"]]
                        ).id,
                        quantity=round(q, 1), unit=s["unit"],
                        reporting_year=year, reporting_month=month,
                        data_source="DEMO synthetic activity data",
                        notes=f"DEMO planted anomaly: quantity x{mult}" if mult else None,
                    ))

        print(f"\nSeeded company id {company.id}. Tonnes by year, scope and category:")
        for row in db.execute(text(
            "SELECT reporting_year, scope::text, category::text, ROUND(SUM(co2_tonnes)::numeric, 1) "
            "FROM emission_records WHERE company_id = :c GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
        ), {"c": company.id}):
            print(f"  {row[0]}  {row[1]:<8} {row[2]:<24} {row[3]:>10}")
        print("Planted anomalies:")
        for row in db.execute(text(
            "SELECT id, reporting_year, reporting_month, scope::text, category::text, co2_tonnes "
            "FROM emission_records WHERE company_id = :c AND notes LIKE 'DEMO planted%' ORDER BY id"
        ), {"c": company.id}):
            print(f"  record {row[0]} | {row[1]}-{row[2]:02d} | {row[3]} / {row[4]} | {row[5]:.2f} t")
    except HTTPException as exc:
        sys.exit(f"Pipeline refused an entry: {exc.detail}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
