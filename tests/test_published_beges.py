"""
Checks against the public BEGES of Salesforce.com France, financial year 2023
(https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/legal/misc/BEGES_Salesforce_2023.pdf).
Figures are transcribed from the two pages of the filing. The filing's "combustibles 0.0135" line
is taken to be the upstream ('Amont') part of the electricity factor.
"""
from dataclasses import dataclass

import pytest

from app.models.emission import EmissionCategory as C, EmissionScope as S
from app.services.allocation import plan_allocation
from app.services.calculation import calculate_emissions


@dataclass
class Comp:
    post_type: str
    kg_co2e_per_unit: float


def _tonnes(quantity, unit, kg_per_unit, factor_unit):
    return calculate_emissions(quantity, unit, kg_per_unit, factor_unit).co2_tonnes


def test_scope1_gas_uses_the_combustion_factor_only():
    comps = [Comp("Combustion", 0.201), Comp("Amont", 0.0389172)]
    plan = plan_allocation(S.SCOPE_1, C.STATIONARY_COMBUSTION, 0.201 + 0.0389172, comps)
    assert plan.slices[0].scope == S.SCOPE_1
    assert plan.slices[1].scope == S.SCOPE_3
    assert _tonnes(12_978, "kWh PCI", plan.slices[0].kg_co2e_per_unit, "kWh PCI") == pytest.approx(2.61, abs=0.005)


def test_scope2_electricity_books_generation_only():
    comps = [Comp("Combustion à la centrale", 0.0338), Comp("Amont", 0.0135),
             Comp("Transport et distribution", 0.00474)]
    plan = plan_allocation(S.SCOPE_2, C.PURCHASED_ELECTRICITY, 0.05204, comps)
    grid_kwh = 1_333_495 + 225_080 + 156_725 + 3_642_620
    assert grid_kwh == 5_357_920
    assert plan.slices[0].scope == S.SCOPE_2
    assert [s.scope for s in plan.slices[1:]] == [S.SCOPE_3, S.SCOPE_3]
    assert _tonnes(grid_kwh, "kWh", plan.slices[0].kg_co2e_per_unit, "kWh") == pytest.approx(181.10, abs=0.005)


def test_steam_non_operated_site_and_refrigerants():
    assert _tonnes(529_437, "kWh", 0.18, "kWh") == pytest.approx(95.30, abs=0.005)
    assert _tonnes(83_432, "kWh", 0.05204, "kWh") == pytest.approx(4.34, abs=0.005)
    fugitive = _tonnes(63.261, "kg", 4800, "kg") + _tonnes(18.483, "kg", 1920, "kg")
    assert fugitive == pytest.approx(339.14, abs=0.005)
