import math

import pandas as pd
import pytest

from app.ml.anomaly_detector import build_anomaly_features
from app.ml.feature_engineering import stream_key


def test_label_identifies_the_stream_across_factor_changes():
    assert stream_key(101, "Combustion à la centrale", "Grid electricity") == \
        stream_key(202, "Combustion à la centrale", " grid electricity ")


def test_without_a_label_the_factor_id_defines_the_stream():
    assert stream_key(101, "Amont") != stream_key(202, "Amont")


def test_log_features_treat_spikes_and_drops_symmetrically():
    def log_ratio(factor):
        rows = [
            {"company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
             "co2_tonnes": 100.0 * (factor if i == 5 else 1.0),
             "reporting_year": 2022 + i // 12, "reporting_month": i % 12 + 1}
            for i in range(24)
        ]
        return build_anomaly_features(pd.DataFrame(rows)).sort_index().loc[5, "log_ratio_to_median"]

    assert log_ratio(4.0) == pytest.approx(-log_ratio(0.25))


def test_same_month_reference_removes_seasonality():
    rows = []
    for i in range(36):
        month = i % 12 + 1
        seasonal = 1 + 0.45 * math.cos(2 * math.pi * (month - 1) / 12)
        rows.append({
            "company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
            "co2_tonnes": 100.0 * seasonal * (2.0 if i == 18 else 1.0),   # doubled in a seasonal trough
            "reporting_year": 2022 + i // 12, "reporting_month": month,
        })
    row = build_anomaly_features(pd.DataFrame(rows)).sort_index().loc[18]
    assert abs(row["log_ratio_same_month"]) > abs(row["log_ratio_to_median"]) + 0.3
