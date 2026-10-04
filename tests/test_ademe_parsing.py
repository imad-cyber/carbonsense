from datetime import date
from app.ingest.ademe import (
    SKIP_NOT_ELEMENT, SKIP_NOT_FACTOR, SKIP_NO_TOTAL, SKIP_UNIT_FORMAT,
    SKIP_NOT_POSTE, parse_component,
    clean_text, full_name, norm, parse_date, parse_factor_unit, parse_row, to_float,
)


def make_row(**overrides):
    row = {
        "Type_Ligne": "Elément",
        "Identifiant_de_l'élément": "99001",
        "Type_de_l'élément": "Facteur d'émission",
        "Statut_de_l'élément": "Valide générique",
        "Nom_base_français": "TEST Carburant fictif",
        "Nom_attribut_français": "usage test",
        "Nom_frontière_français": "",
        "Code_de_la_catégorie": "Test > Fictif",
        "Unité_français": "kgCO2e/litre",
        "Localisation_géographique": "France continentale",
        "Période_de_validité": "31/12/2030",
        "Incertitude": 10,
        "Total_poste_non_décomposé": 1.5,
        "_id": "abc",
        "_score": None,
    }
    row.update(overrides)
    return row


def test_norm_ignores_accents_case_punctuation_and_unicode_form():
    assert norm("Unité_français") == "unite_francais"
    assert norm("Identifiant_de_l'élément") == "identifiant_de_l_element"
    assert norm("e\u0301le\u0301ment") == norm("élément")  # decomposed accents


def test_clean_text_removes_stray_quotes_and_tabs():
    assert clean_text('"""\tSalade César au poulet (salade verte"""') == "Salade César au poulet (salade verte"
    assert clean_text('"""Barre céréalière """"équilibre"""" aux fruits"""') == "Barre céréalière équilibre aux fruits"


def test_full_name_joins_non_empty_parts():
    assert full_name("Gaz", "", "Combustion") == "Gaz - Combustion"


def test_parse_factor_unit():
    assert parse_factor_unit("kgCO2e/kg de poids net") == "kg de poids net"
    assert parse_factor_unit("kgCO2e/kWh PCI") == "kWh PCI"
    assert parse_factor_unit("kgCO2e / litre") == "litre"
    assert parse_factor_unit("tCO2e/t") is None
    assert parse_factor_unit("") is None


def test_parse_date_accepts_both_formats():
    assert parse_date("31/12/2023") == date(2023, 12, 31)
    assert parse_date("2021-03-04") == date(2021, 3, 4)
    assert parse_date("n/a") is None


def test_to_float_handles_decimal_commas_and_booleans():
    assert to_float("2,81") == 2.81
    assert to_float(7) == 7.0
    assert to_float(True) is None
    assert to_float("") is None


def test_importable_row_is_parsed():
    factor, reason = parse_row(make_row())
    assert reason is None
    assert factor.source_id == "99001"
    assert factor.name == "TEST Carburant fictif - usage test"
    assert factor.unit == "litre"
    assert factor.kg_co2e_per_unit == 1.5
    assert factor.uncertainty_pct == 10.0
    assert factor.status == "Valide générique"
    assert factor.valid_until == date(2030, 12, 31)
    assert "_id" not in factor.raw and "_score" not in factor.raw


def test_poste_rows_are_skipped():
    assert parse_row(make_row(Type_Ligne="Poste")) == (None, SKIP_NOT_ELEMENT)


def test_source_data_rows_are_skipped():
    row = make_row(**{"Type_de_l'élément": "Données source"})
    assert parse_row(row) == (None, SKIP_NOT_FACTOR)


def test_missing_total_is_reported_not_guessed():
    row = make_row(**{"Total_poste_non_décomposé": None})
    assert parse_row(row) == (None, SKIP_NO_TOTAL)


def test_unexpected_unit_format_is_reported():
    assert parse_row(make_row(**{"Unité_français": "tCO2e/t"})) == (None, SKIP_UNIT_FORMAT)


def test_archived_rows_are_parsed_with_their_status():
    factor, _ = parse_row(make_row(**{"Statut_de_l'élément": "Archivé"}))
    assert factor.status == "Archivé"


def test_missing_uncertainty_stays_none():
    row = make_row()
    del row["Incertitude"]
    factor, _ = parse_row(row)
    assert factor.uncertainty_pct is None

def make_poste(**overrides):
    row = {
        "Type_Ligne": "Poste",
        "Identifiant_de_l'élément": "99001",
        "Type_de_l'élément": "Facteur d'émission",
        "Type_poste": "Combustion",
        "Nom_poste_français": "",
        "Total_poste_non_décomposé": 0.344,
        "CO2f": 0.344, "CH4f": 0, "N2O": 0,
    }
    row.update(overrides)
    return row


def test_component_is_parsed_and_zero_gases_are_dropped():
    c, reason = parse_component(make_poste())
    assert reason is None
    assert (c.source_id, c.post_type, c.kg_co2e_per_unit) == ("99001", "Combustion", 0.344)
    assert c.gases == {"co2f": 0.344}
    assert c.post_name is None


def test_element_rows_are_not_components():
    assert parse_component(make_row()) == (None, SKIP_NOT_POSTE)


def test_component_without_total_is_reported():
    assert parse_component(make_poste(**{"Total_poste_non_décomposé": None})) == (None, SKIP_NO_TOTAL)


def test_sub_geography_is_kept():
    factor, _ = parse_row(make_row(**{"Sous-localisation_géographique_français": "Allemagne"}))
    assert factor.sub_geography == "Allemagne"
