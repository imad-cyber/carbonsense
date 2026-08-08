"""
Generates realistic synthetic emission data for model training.
Run once: python scripts/generate_training_data.py

Design decisions:
- Scope 3 is always the largest (realistic — typically 70-90% of total)
- Emissions have seasonal patterns (heating in winter = more Scope 1 in Dec/Jan)
- Each company has a gradual downward trend (CSRD pressure to reduce)
- Random noise makes the data realistic, not perfectly smooth
"""
import sys
import os
import random
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.company import Company, IndustrySector
from app.models.emission import EmissionRecord, EmissionScope, EmissionCategory

random.seed(42)  # reproducibility — same seed = same data every run


COMPANIES = [
    {"name": "TotalEnergies SE", "sector": IndustrySector.ENERGY,
     "base_s1": 85000, "base_s2": 18000, "base_s3": 420000},
    {"name": "Renault Group", "sector": IndustrySector.MANUFACTURING,
     "base_s1": 45000, "base_s2": 22000, "base_s3": 890000},
    {"name": "Société Générale", "sector": IndustrySector.FINANCE,
     "base_s1": 3200, "base_s2": 8500, "base_s3": 145000},
    {"name": "Carrefour SA", "sector": IndustrySector.RETAIL,
     "base_s1": 28000, "base_s2": 41000, "base_s3": 620000},
    {"name": "Orange SA", "sector": IndustrySector.TECHNOLOGY,
     "base_s1": 5500, "base_s2": 32000, "base_s3": 98000},
]

SCOPE_CATEGORIES = {
    EmissionScope.SCOPE_1: [
        (EmissionCategory.STATIONARY_COMBUSTION, 0.6),
        (EmissionCategory.MOBILE_COMBUSTION, 0.4),
    ],
    EmissionScope.SCOPE_2: [
        (EmissionCategory.PURCHASED_ELECTRICITY, 0.75),
        (EmissionCategory.PURCHASED_HEAT, 0.25),
    ],
    EmissionScope.SCOPE_3: [
        (EmissionCategory.SUPPLY_CHAIN, 0.65),
        (EmissionCategory.BUSINESS_TRAVEL, 0.10),
        (EmissionCategory.EMPLOYEE_COMMUTING, 0.10),
        (EmissionCategory.WASTE, 0.15),
    ],
}


def seasonal_factor(month: int, scope: EmissionScope) -> float:
    """
    Emissions are NOT uniform across months.
    - Scope 1 peaks in winter (heating)
    - Scope 2 peaks in summer (cooling) and winter (lighting)
    - Scope 3 follows economic activity — peaks Q4 (supply chain rush)
    This seasonal signal is what makes the forecasting model non-trivial.
    """
    if scope == EmissionScope.SCOPE_1:
        # Sine wave peaking in January (month 1)
        return 1.0 + 0.25 * math.cos(2 * math.pi * (month - 1) / 12)
    elif scope == EmissionScope.SCOPE_2:
        return 1.0 + 0.15 * math.cos(2 * math.pi * (month - 7) / 12)
    else:
        return 1.0 + 0.10 * math.cos(2 * math.pi * (month - 10) / 12)


def annual_reduction(year: int, base_year: int = 2022) -> float:
    """
    Companies reduce emissions ~3% per year under CSRD pressure.
    Compounding reduction: year 2 is 97% of year 1, year 3 is 94%, etc.
    """
    years_elapsed = year - base_year
    return 0.97 ** years_elapsed


db = SessionLocal()

try:
    print("Creating companies...")
    company_ids = {}

    for c_data in COMPANIES:
        existing = db.query(Company).filter(
            Company.name == c_data["name"]
        ).first()

        if not existing:
            company = Company(
                name=c_data["name"],
                sector=c_data["sector"],
                country="France",
                employee_count=random.randint(5000, 120000),
                annual_revenue_eur=random.randint(500000, 50000000),
            )
            db.add(company)
            db.flush()  # flush to get the ID without full commit
            company_ids[c_data["name"]] = (company.id, c_data)
            print(f"  Created: {c_data['name']} (id={company.id})")
        else:
            company_ids[c_data["name"]] = (existing.id, c_data)
            print(f"  Already exists: {c_data['name']} (id={existing.id})")

    print("\nGenerating emission records...")
    record_count = 0

    for company_name, (company_id, c_data) in company_ids.items():
        for year in [2022, 2023, 2024]:
            reduction = annual_reduction(year)

            for month in range(1, 13):
                for scope, categories in SCOPE_CATEGORIES.items():
                    base_key = f"base_s{scope.value[-1]}"
                    base_value = c_data[base_key]

                    # Monthly base = annual total / 12
                    monthly_base = base_value / 12

                    # Apply seasonal pattern and annual reduction
                    seasonal = seasonal_factor(month, scope)
                    noise = random.gauss(1.0, 0.05)  # ±5% random noise

                    monthly_total = monthly_base * seasonal * reduction * noise

                    for category, proportion in categories:
                        co2 = monthly_total * proportion
                        # Add category-level noise
                        co2 *= random.gauss(1.0, 0.03)

                        record = EmissionRecord(
                            company_id=company_id,
                            scope=scope,
                            category=category,
                            co2_tonnes=round(max(co2, 0.1), 2),
                            reporting_year=year,
                            reporting_month=month,
                            data_source="synthetic_training_data",
                        )
                        db.add(record)
                        record_count += 1

    db.commit()
    print(f"\n Done. Created {record_count} emission records across "
          f"{len(company_ids)} companies (2022–2024)")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()