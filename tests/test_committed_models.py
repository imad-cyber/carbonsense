import os
import shutil
import pytest

from app.core.config import settings
from app.ml.inference import inference_service
from app.ml.model_registry import load_model

# Ensure committed models from repo root are copied into test settings.MODEL_DIR
for filename in ("forecasting_latest.joblib", "anomaly_detector_latest.joblib"):
    src = os.path.join("models", filename)
    dst = os.path.join(settings.MODEL_DIR, filename)
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)

inference_service._anomaly_payload = None
inference_service._forecasting_payload = None


def test_committed_models_exist():
    for name in ("forecasting", "anomaly_detector"):
        assert load_model(name) is not None, f"models/{name}_latest.joblib is missing"


def test_committed_detector_flags_a_planted_spike():
    rows = [
        {"record_id": i, "company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
         "co2_tonnes": 600.0 if i == 20 else 100.0,
         "reporting_year": 2022 + i // 12, "reporting_month": i % 12 + 1}
        for i in range(36)
    ]
    assert inference_service.detect_anomalies(rows)[20]["is_anomaly"] is True


def test_committed_forecaster_predicts_the_next_month():
    records = [
        {"company_id": 1, "scope": "scope_1", "category": "stationary_combustion", "co2_tonnes": 100.0,
         "reporting_year": 2023 + i // 12, "reporting_month": i % 12 + 1}
        for i in range(24)
    ]
    out = inference_service.predict_emissions(1, "scope_1", "stationary_combustion", 2025, 1, records)
    assert 50 < out["predicted_co2_tonnes"] < 200
