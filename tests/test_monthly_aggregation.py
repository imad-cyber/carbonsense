import pandas as pd
import pytest

from app.ml.anomaly_detector import build_anomaly_features
from app.ml.feature_engineering import engineer_forecasting_features, stream_key


def _rows(months, values=(100.0,)):
    return [
        {"company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
         "co2_tonnes": v, "reporting_year": 2022 + i // 12, "reporting_month": i % 12 + 1}
        for i in months for v in values
    ]


def test_several_records_in_one_month_are_summed_into_one_row():
    feats = engineer_forecasting_features(pd.DataFrame(_rows(range(14), values=(60.0, 40.0))))
    assert len(feats) == 14
    assert (feats["co2_tonnes"] == 100.0).all()
    assert feats["lag_1_month"].iloc[5] == 100.0   # last month's sum, not one of its parts


def test_a_gap_in_a_monthly_series_is_refused():
    with pytest.raises(ValueError, match="gaps"):
        engineer_forecasting_features(pd.DataFrame(_rows([i for i in range(14) if i != 6])))


def test_annual_records_are_not_treated_as_a_month():
    rows = _rows(range(14)) + [
        {"company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
         "co2_tonnes": 999.0, "reporting_year": 2022, "reporting_month": 0}
    ]
    feats = engineer_forecasting_features(pd.DataFrame(rows))
    assert len(feats) == 14 and feats["co2_tonnes"].max() == 100.0


def test_streams_in_one_category_are_scored_separately():
    rows = []
    for i in range(12):
        for stream, base, step in (("1:Combustion", 1000.0, 1.0), ("2:Combustion", 10.0, 0.01)):
            rows.append({
                "company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
                "co2_tonnes": base + step * i, "reporting_year": 2024,
                "reporting_month": i + 1, "stream": stream,
            })
    feats = build_anomaly_features(pd.DataFrame(rows))
    assert feats["ratio_to_median"].between(0.9, 1.1).all()


def test_stream_key():
    assert stream_key(None, None) == "direct"
    assert stream_key(4603, "Amont") == "4603:Amont"
    assert stream_key(4603, None) == "4603:total"
