"""ML pipeline tests — feature engineering, anomaly detection, model registry."""
import numpy as np
import pandas as pd
import pytest

from app.ml.feature_engineering import (
    engineer_forecasting_features,
    get_feature_columns,
)
from app.ml.model_registry import load_model, save_model


def _sample_dataframe(months: int = 24) -> pd.DataFrame:
    """Synthetic emission history: one company, one scope/category series."""
    rows = []
    rng = np.random.default_rng(42)
    for i in range(months):
        year = 2022 + i // 12
        month = i % 12 + 1
        rows.append({
            "id": i + 1,
            "company_id": 1,
            "scope": "scope_1",
            "category": "stationary_combustion",
            "co2_tonnes": 1000 + 200 * np.sin(2 * np.pi * month / 12) + rng.normal(0, 20),
            "reporting_year": year,
            "reporting_month": month,
            "data_source": "test",
        })
    return pd.DataFrame(rows)


def test_feature_engineering_produces_lag_columns():
    df = engineer_forecasting_features(_sample_dataframe())
    assert "lag_1_month" in df.columns
    assert "lag_12_months" in df.columns
    # After 12 months of history the lags must be populated
    assert df["lag_1_month"].notna().sum() >= 12
    assert df["lag_12_months"].notna().sum() >= 1


def test_cyclical_encoding_range():
    df = engineer_forecasting_features(_sample_dataframe())
    assert df["month_sin"].between(-1, 1).all()
    assert df["month_cos"].between(-1, 1).all()


def test_feature_columns_consistent():
    assert get_feature_columns() == get_feature_columns()
    assert len(get_feature_columns()) > 0


def test_anomaly_detection_returns_scores():
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import RobustScaler

    from app.ml.anomaly_detector import build_anomaly_features

    df = _sample_dataframe()
    # Inject an obvious anomaly
    df.loc[len(df) - 1, "co2_tonnes"] = 50_000

    df_features = build_anomaly_features(df)
    feature_cols = ["co2_tonnes", "z_score", "ratio_to_median",
                    "mom_change", "reporting_month"]
    X = df_features[feature_cols].fillna(0)

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)
    model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    model.fit(X_scaled)

    predictions = model.predict(X_scaled)
    scores = model.decision_function(X_scaled)

    # Every record gets an is_anomaly verdict and a score
    assert len(predictions) == len(df)
    assert len(scores) == len(df)
    assert set(predictions).issubset({-1, 1})
    # The injected outlier must be flagged
    assert predictions[-1] == -1


def test_forecast_requires_history(db_session):
    """predict_emissions raises ValueError with < 12 history records."""
    from xgboost import XGBRegressor

    from app.ml.inference import EmissionInferenceService

    # A model must exist for the check to be reached — train a dummy one
    feature_cols = get_feature_columns()
    X_dummy = pd.DataFrame(
        np.random.default_rng(0).random((20, len(feature_cols))),
        columns=feature_cols,
    )
    y_dummy = pd.Series(np.random.default_rng(1).random(20) * 100)
    dummy_model = XGBRegressor(n_estimators=5, max_depth=2)
    dummy_model.fit(X_dummy, y_dummy)
    save_model(dummy_model, "forecasting", metadata={"test": True})

    service = EmissionInferenceService()
    with pytest.raises(ValueError, match="12 months"):
        service.predict_emissions(
            db_session,
            company_id=999_999,  # no records for this company
            scope="scope_1",
            category="stationary_combustion",
            reporting_year=2025,
            reporting_month=6,
        )


def test_model_registry_save_load():
    from sklearn.ensemble import IsolationForest

    model = IsolationForest(n_estimators=10, random_state=0)
    model.fit(np.random.default_rng(2).random((30, 3)))

    save_model(model, "registry_roundtrip_test", metadata={"purpose": "test"})
    payload = load_model("registry_roundtrip_test")

    assert payload is not None
    assert isinstance(payload["model"], IsolationForest)
    assert payload["metadata"]["purpose"] == "test"
    assert payload["name"] == "registry_roundtrip_test"
