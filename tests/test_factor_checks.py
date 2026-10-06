from datetime import date
from app.services.factor_checks import factor_warnings


def test_archived_factor_is_flagged():
    w = factor_warnings(status="Archivé", valid_until=None, uncertainty_pct=10, reporting_year=2024)
    assert len(w) == 1 and "archived" in w[0]


def test_expired_validity_is_flagged():
    w = factor_warnings(status="Valide générique", valid_until=date(2023, 12, 31),
                        uncertainty_pct=10, reporting_year=2024)
    assert len(w) == 1 and "2023-12-31" in w[0]


def test_missing_uncertainty_is_flagged():
    w = factor_warnings(status="Valide générique", valid_until=None,
                        uncertainty_pct=None, reporting_year=2024)
    assert len(w) == 1 and "uncertainty" in w[0]


def test_clean_factor_has_no_warnings():
    assert factor_warnings(status="Valide générique", valid_until=date(2030, 1, 1),
                           uncertainty_pct=5, reporting_year=2025) == []

def test_monthly_record_inside_validity_is_not_flagged():
    assert factor_warnings(status="Valide générique", valid_until=date(2025, 2, 28),
                           uncertainty_pct=5, reporting_year=2025, reporting_month=1) == []


def test_month_after_validity_is_flagged():
    w = factor_warnings(status="Valide générique", valid_until=date(2025, 2, 28),
                        uncertainty_pct=5, reporting_year=2025, reporting_month=3)
    assert len(w) == 1 and "2025-03-31" in w[0]


def test_annual_record_running_past_validity_is_flagged():
    w = factor_warnings(status="Valide générique", valid_until=date(2025, 2, 28),
                        uncertainty_pct=5, reporting_year=2025)
    assert len(w) == 1 and "2025-12-31" in w[0]
