import numpy as np
import pandas as pd
import pytest

from app.ml.anomaly_detector import build_anomaly_features, flag_most_unusual
from app.ml.feature_engineering import monitored_value


def test_monitored_value_recovers_the_quantity():
    assert monitored_value(33.8, 0.0338) == pytest.approx(1_000_000)
    assert monitored_value(5.0, None) == 5.0
    assert monitored_value(5.0, 0) == 5.0


def test_a_revised_emission_factor_is_not_an_anomaly():
    factors = {2022: 0.0338, 2023: 0.0357, 2024: 0.0300}
    rows = []
    for i in range(36):
        year, month = 2022 + i // 12, i % 12 + 1
        tonnes = 1_000_000 * factors[year] / 1000.0   # constant activity: 1,000,000 kWh
        rows.append({
            "company_id": 1, "scope": "scope_2", "category": "purchased_electricity",
            "co2_tonnes": tonnes, "monitored": monitored_value(tonnes, factors[year]),
            "reporting_year": year, "reporting_month": month,
        })
    df = pd.DataFrame(rows)
    assert build_anomaly_features(df).sort_index()["log_ratio_to_median"].abs().max() < 1e-9
    # judged on tonnes instead, the factor revision shows up as a level shift
    tonnes_only = build_anomaly_features(df.drop(columns="monitored")).sort_index()
    assert tonnes_only["log_ratio_to_median"].abs().max() > 0.05


def test_flags_exactly_the_most_unusual_fraction():
    flagged = flag_most_unusual(np.arange(100, dtype=float), 0.05)   # lowest = most unusual
    assert flagged.sum() == 5 and flagged[:5].all()


def test_flags_at_least_one_record():
    assert flag_most_unusual(np.array([3.0, 1.0, 2.0]), 0.01).tolist() == [False, True, False]


def test_empty_batch():
    assert flag_most_unusual(np.array([]), 0.05).size == 0
