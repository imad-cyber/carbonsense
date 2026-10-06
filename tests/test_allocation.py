from dataclasses import dataclass

import pytest

from app.models.emission import EmissionCategory as C, EmissionScope as S
from app.services.allocation import AllocationError, plan_allocation


@dataclass
class Comp:
    post_type: str
    kg_co2e_per_unit: float


GAS_2022_PCS = [Comp("Combustion", 0.181), Comp("Amont", 0.0344)]          # ADEME 37133, total 0.215
DIESEL_B7 = [Comp("Combustion", 2.49), Comp("Amont", 0.609)]               # ADEME 25775, total 3.1
ELECTRICITY = [Comp("Combustion à la centrale", 0.0569), Comp("Amont", 0.0129),
               Comp("Transport et distribution", 0.0087)]                  # ADEME 26825, total 0.0785


def test_scope1_gas_books_combustion_only_and_moves_upstream_to_scope3():
    plan = plan_allocation(S.SCOPE_1, C.STATIONARY_COMBUSTION, 0.215, GAS_2022_PCS)
    direct, upstream = plan.slices
    assert (direct.scope, direct.kg_co2e_per_unit) == (S.SCOPE_1, 0.181)
    assert (upstream.scope, upstream.category) == (S.SCOPE_3, C.FUEL_ENERGY_RELATED)
    assert upstream.post_type == "Amont" and upstream.kg_co2e_per_unit == 0.0344


def test_diesel_in_mobile_combustion():
    plan = plan_allocation(S.SCOPE_1, C.MOBILE_COMBUSTION, 3.1, DIESEL_B7)
    assert plan.slices[0].category == C.MOBILE_COMBUSTION
    assert plan.slices[0].kg_co2e_per_unit == 2.49


def test_electricity_generation_is_scope2_and_upstream_and_losses_are_scope3():
    plan = plan_allocation(S.SCOPE_2, C.PURCHASED_ELECTRICITY, 0.0785, ELECTRICITY)
    first, *rest = plan.slices
    assert (first.scope, first.kg_co2e_per_unit) == (S.SCOPE_2, 0.0569)
    assert {s.post_type for s in rest} == {"Amont", "Transport et distribution"}
    assert all(s.scope == S.SCOPE_3 and s.category == C.FUEL_ENERGY_RELATED for s in rest)


def test_scope3_purchases_are_not_split():
    plan = plan_allocation(S.SCOPE_3, C.SUPPLY_CHAIN, 2.5, GAS_2022_PCS)
    assert [(s.post_type, s.kg_co2e_per_unit) for s in plan.slices] == [("total", 2.5)]
    assert plan.warnings == []


def test_energy_factor_without_breakdown_warns():
    plan = plan_allocation(S.SCOPE_1, C.STATIONARY_COMBUSTION, 0.2, [])
    assert len(plan.slices) == 1 and plan.slices[0].kg_co2e_per_unit == 0.2
    assert "no published breakdown" in plan.warnings[0]


def test_unknown_post_type_is_refused():
    comps = [Comp("Combustion", 1.0), Comp("Carburant (amont/combustion)", 0.5)]
    with pytest.raises(AllocationError, match="unhandled"):
        plan_allocation(S.SCOPE_1, C.MOBILE_COMBUSTION, 1.5, comps)


def test_scope2_factor_with_scope1_style_post_is_refused():
    with pytest.raises(AllocationError):
        plan_allocation(S.SCOPE_2, C.PURCHASED_ELECTRICITY, 1.0, [Comp("Combustion", 1.0)])


def test_district_heat_with_components_is_refused():
    with pytest.raises(AllocationError, match="not supported"):
        plan_allocation(S.SCOPE_2, C.PURCHASED_HEAT, 0.1, [Comp("Combustion", 0.1)])


def test_posts_that_do_not_add_up_are_refused():
    comps = [Comp("Combustion", 1.0), Comp("Amont", 0.1)]
    with pytest.raises(AllocationError, match="do not add up"):
        plan_allocation(S.SCOPE_1, C.STATIONARY_COMBUSTION, 2.0, comps)


def test_zero_upstream_does_not_create_a_record():
    plan = plan_allocation(S.SCOPE_1, C.STATIONARY_COMBUSTION, 1.0,
                           [Comp("Combustion", 1.0), Comp("Amont", 0.0)])
    assert len(plan.slices) == 1
