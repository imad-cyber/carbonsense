import pandas as pd
from app.ml.anomaly_detector import build_anomaly_features


def test_features_can_be_realigned_with_input_order():
    """
    build_anomaly_features sorts rows internally (needed for mom_change).
    sort_index() must restore the original input row order so that anomaly
    scores are attached to the correct records in the API response.
    """
    # Rows deliberately in reverse chronological order, two series interleaved
    rows = [
        {
            "company_id": c,
            "scope": "scope_1",
            "category": "stationary_combustion",
            "co2_tonnes": 100.0 * c + m,
            "reporting_year": 2024,
            "reporting_month": m,
        }
        for m in range(12, 0, -1)
        for c in (2, 1)
    ]
    df = pd.DataFrame(rows)
    feats = build_anomaly_features(df).sort_index()
    assert feats["co2_tonnes"].tolist() == df["co2_tonnes"].tolist()
