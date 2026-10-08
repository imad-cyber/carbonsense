"""
Compare CarbonSense with the public BEGES of Salesforce.com France (financial year 2023).
Inputs and published figures are transcribed from the filing. Factors are looked up in the
loaded ADEME Base Carbone (V23.6), which can differ from the tool version the filing used.

  python scripts/reproduce_beges.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from app.db.database import SessionLocal
from app.ingest.ademe import SOURCE, norm
from app.models.emission import EmissionCategory, EmissionScope
from app.models.emission_factor import EmissionFactor
from app.services.allocation import plan_allocation
from app.services.calculation import calculate_emissions

GRID_KWH = 1_333_495 + 225_080 + 156_725 + 3_642_620   # sites operated by the company

LINES = [
    dict(label="1.1 fixed combustion, natural gas", scope=EmissionScope.SCOPE_1,
         category=EmissionCategory.STATIONARY_COMBUSTION,
         factor_name="Gaz naturel - 2022 - mix moyen - consommation", unit="kWh PCI",
         quantity=12_978, published_t=2.61,
         published_factors={"combustion": 0.201, "amont": 0.0389172}),
    dict(label="2.1 electricity, operated grid sites", scope=EmissionScope.SCOPE_2,
         category=EmissionCategory.PURCHASED_ELECTRICITY,
         factor_name="Electricité - 2022 - mix moyen - consommation", unit="kWh",
         quantity=GRID_KWH, published_t=181.10,
         published_factors={"combustion_a_la_centrale": 0.0338, "amont": 0.0135,
                            "transport_et_distribution": 0.00474}),
]

# Arithmetic only: quantity x the factor as printed in the filing (not looked up in Base Carbone)
ARITHMETIC = [
    ("2.2 steam, 529,437 kWh x 0.18", 529_437 * 0.18 / 1000, 95.30),
    ("6.1 non-operated site, 83,432 kWh x total electricity factor", 83_432 * 0.05204 / 1000, 4.34),
    ("1.4 refrigerants (kg x GWP)", (63.261 * 4800 + 18.483 * 1920) / 1000, 339.14),
]


def main() -> None:
    db = SessionLocal()
    try:
        for line in LINES:
            print(f"\n{line['label']}: {line['quantity']:,} {line['unit']}")
            matches = (
                db.query(EmissionFactor)
                .filter(
                    EmissionFactor.source == SOURCE,
                    EmissionFactor.geography == "France continentale",
                    EmissionFactor.name.ilike(line["factor_name"]),
                    EmissionFactor.unit.ilike(line["unit"]),
                )
                .all()
            )
            if not matches:
                print("  factor not found in the loaded data; search the API and send me the names")
                continue
            for f in matches:
                print(f"  factor {f.source_id} | {f.name} | {f.status} | total {f.kg_co2e_per_unit}")
                for c in f.components:
                    pub = line["published_factors"].get(norm(c.post_type))
                    note = "" if not pub else (
                        f"  (filing {pub}, difference {100 * (c.kg_co2e_per_unit - pub) / pub:+.1f}%)"
                    )
                    print(f"      {c.post_type}: {c.kg_co2e_per_unit}{note}")
                plan = plan_allocation(line["scope"], line["category"], f.kg_co2e_per_unit, f.components)
                direct = plan.slices[0]
                ours = calculate_emissions(
                    line["quantity"], line["unit"], direct.kg_co2e_per_unit, f.unit
                ).co2_tonnes
                diff = 100 * (ours - line["published_t"]) / line["published_t"]
                print(f"  CarbonSense {direct.scope.value}: {ours:,.2f} t | "
                      f"filing {line['published_t']:,.2f} t | difference {diff:+.2f}%")
        print("\nArithmetic only (quantity x factor as printed in the filing):")
        for label, ours, published in ARITHMETIC:
            print(f"  {label}: {ours:,.2f} t | filing {published:,.2f} t")
    finally:
        db.close()


if __name__ == "__main__":
    main()
