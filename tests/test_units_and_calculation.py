import pytest
from app.services.calculation import calculate_emissions
from app.services.units import UnitMismatchError, convert_quantity


def test_same_unit_is_unchanged():
    assert convert_quantity(5, "kWh", "kWh") == 5


def test_mwh_to_kwh():
    assert convert_quantity(2, "MWh", "kWh") == pytest.approx(2000)


def test_litre_aliases_and_case():
    assert convert_quantity(3, "litres", "L") == 3


def test_cubic_metres_to_litres():
    assert convert_quantity(5, "m³", "L") == pytest.approx(5000)


def test_tonnes_to_kg():
    assert convert_quantity(1.5, "tonnes", "kg") == pytest.approx(1500)


def test_heating_value_bases_are_not_interchangeable():
    with pytest.raises(UnitMismatchError):
        convert_quantity(1, "kWh", "kWh PCI")


def test_different_dimensions_are_rejected():
    with pytest.raises(UnitMismatchError):
        convert_quantity(1, "kWh", "kg")


def test_basic_calculation():
    c = calculate_emissions(1000, "kWh", 0.05, "kWh")
    assert c.co2_tonnes == pytest.approx(0.05)
    assert c.co2_tonnes_low is None and c.co2_tonnes_high is None


def test_calculation_converts_units_first():
    c = calculate_emissions(2, "MWh", 0.05, "kWh")
    assert c.quantity_in_factor_unit == pytest.approx(2000)
    assert c.co2_tonnes == pytest.approx(0.1)


def test_uncertainty_range_comes_from_the_factor():
    c = calculate_emissions(1000, "kWh", 0.05, "kWh", uncertainty_pct=20)
    assert c.co2_tonnes_low == pytest.approx(0.04)
    assert c.co2_tonnes_high == pytest.approx(0.06)


def test_negative_quantity_is_rejected():
    with pytest.raises(ValueError):
        calculate_emissions(-1, "kWh", 0.05, "kWh")


def test_negative_factor_is_rejected():
    with pytest.raises(ValueError):
        calculate_emissions(1, "kWh", -0.05, "kWh")


def test_unit_mismatch_propagates():
    with pytest.raises(UnitMismatchError):
        calculate_emissions(1, "kg", 0.05, "kWh")

def test_conversion_inside_a_heating_value_basis():
    assert convert_quantity(2, "MWh PCS", "kWh PCS") == pytest.approx(2000)
    assert convert_quantity(1, "GJ PCI", "kWh PCI") == pytest.approx(277.7778, rel=1e-5)


def test_pci_and_pcs_are_never_mixed():
    with pytest.raises(UnitMismatchError):
        convert_quantity(1, "kWh PCI", "kWh PCS")


def test_case_variants_of_ademe_units_match():
    assert convert_quantity(4, "KWh PCI", "kWh PCI") == 4
    assert convert_quantity(4, "Litre", "litre") == 4


def test_tonne_km_spellings_are_the_same_unit():
    assert convert_quantity(7, "tonne.km", "t.km") == 7


def test_tep_is_not_converted():
    with pytest.raises(UnitMismatchError):
        convert_quantity(1, "tep PCI", "kWh PCI")
