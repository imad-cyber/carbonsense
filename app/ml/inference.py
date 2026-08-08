"""
EmissionInferenceService — production inference layer.

Loads the latest trained models from the model registry (lazily, once)
and serves forecasts, anomaly scans and feature-importance queries.
The service degrades gracefully: if no model is trained yet, endpoints
return a clear 503 instead of crashing.
"""
import logging

import numpy as np
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ml.feature_engineering import (
    engineer_forecasting_features,
    get_feature_columns,
    load_emission_dataframe,
)
from app.ml.anomaly_detector import build_anomaly_features
from app.ml.explainability import explain_prediction, get_global_feature_importance
from app.ml.model_registry import load_model, model_exists

logger = logging.getLogger(__name__)

ANOMALY_FEATURE_COLS = [
    "co2_tonnes",
    "z_score",
    "ratio_to_median",
    "mom_change",
    "reporting_month",
]


class EmissionInferenceService:
    """
    Singleton service that keeps trained models in memory.

    Loading a joblib model from disk takes ~100ms — doing it per-request
    would dominate latency. Loading once and caching in the process is
    the standard pattern for model serving.
    """

    def __init__(self):
        self._forecasting_payload: dict | None = None
        self._anomaly_payload: dict | None = None

    # ── Model loading ────────────────────────────────────────────────────

    def _get_forecasting_model(self):
        if self._forecasting_payload is None:
            self._forecasting_payload = load_model("forecasting")
        if self._forecasting_payload is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Forecasting model not trained yet — run scripts/train_models.py",
            )
        return self._forecasting_payload["model"]

    def _get_anomaly_model(self):
        if self._anomaly_payload is None:
            self._anomaly_payload = load_model("anomaly_detector")
        if self._anomaly_payload is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Anomaly detector not trained yet — run scripts/train_models.py",
            )
        bundle = self._anomaly_payload["model"]
        return bundle["model"], bundle["scaler"]

    def reload_models(self) -> None:
        """Clear the in-memory cache so the next request loads fresh models."""
        self._forecasting_payload = None
        self._anomaly_payload = None
        logger.info("Inference model cache cleared — will reload on next request")

    def status(self) -> dict:
        return {
            "forecasting_model": model_exists("forecasting"),
            "anomaly_detector": model_exists("anomaly_detector"),
        }

    # ── Forecasting ──────────────────────────────────────────────────────

    def predict_emissions(
        self,
        db: Session,
        company_id: int,
        scope: str,
        category: str,
        reporting_year: int,
        reporting_month: int,
    ) -> dict:
        """
        Forecast CO2 emissions for one company/scope/category/month.

        Builds the same features used at training time by appending the
        future period to the company's history, engineering features and
        taking the final row. Raises ValueError with < 12 history records.
        """
        model = self._get_forecasting_model()

        df = load_emission_dataframe(db, company_id=company_id)
        if not df.empty:
            df = df[(df["scope"] == scope) & (df["category"] == category)]

        if df.empty or len(df) < 12:
            raise ValueError(
                f"Need at least 12 months of history for company {company_id}, "
                f"{scope}/{category} — found {0 if df.empty else len(df)} records."
            )

        future_row = pd.DataFrame([{
            "id": -1,
            "company_id": company_id,
            "scope": scope,
            "category": category,
            "co2_tonnes": np.nan,
            "reporting_year": reporting_year,
            "reporting_month": reporting_month,
            "data_source": "forecast",
        }])
        df_all = pd.concat([df, future_row], ignore_index=True)

        df_features = engineer_forecasting_features(df_all)
        target_row = df_features[df_features["id"] == -1]
        if target_row.empty:
            raise ValueError("Failed to build features for the forecast period")

        # Rolling stats over NaN target propagate — backfill from history
        history_features = df_features[df_features["id"] != -1]
        fill_values = {
            "lag_1_month": history_features["co2_tonnes"].iloc[-1],
            "lag_12_months": history_features["co2_tonnes"].tail(12).iloc[0],
            "rolling_mean_3m": history_features["co2_tonnes"].tail(3).mean(),
            "rolling_std_12m": history_features["co2_tonnes"].tail(12).std() or 0.0,
            "yoy_change": 0.0,
        }
        target_row = target_row.fillna(fill_values)

        X_row = target_row.reindex(columns=get_feature_columns(), fill_value=0)
        X_row = X_row.fillna(0).astype(float)

        prediction = float(model.predict(X_row)[0])
        prediction = max(prediction, 0.0)  # emissions cannot be negative

        explanation = explain_prediction(model, X_row)

        return {
            "company_id": company_id,
            "scope": scope,
            "category": category,
            "reporting_year": reporting_year,
            "reporting_month": reporting_month,
            "predicted_co2_tonnes": round(prediction, 2),
            "explanation": explanation,
        }

    # ── Anomaly detection ────────────────────────────────────────────────

    def detect_anomalies(self, db: Session, company_id: int, year: int) -> dict:
        """
        Score all of a company's records for a given year with the
        Isolation Forest. Features are computed over the company's FULL
        history so group statistics (z-score, ratio-to-median) are stable.
        """
        model, scaler = self._get_anomaly_model()

        df = load_emission_dataframe(db, company_id=company_id)
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No emission records found for company {company_id}",
            )

        df_features = build_anomaly_features(df)
        df_year = df_features[df_features["reporting_year"] == year]
        if df_year.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No emission records for company {company_id} in {year}",
            )

        X = df_year[ANOMALY_FEATURE_COLS].fillna(0)
        X_scaled = scaler.transform(X)

        predictions = model.predict(X_scaled)         # -1 = anomaly, 1 = normal
        scores = model.decision_function(X_scaled)    # lower = more anomalous

        records = []
        anomaly_count = 0
        for (_, row), pred, score in zip(df_year.iterrows(), predictions, scores):
            is_anomaly = bool(pred == -1)
            severity = None
            if is_anomaly:
                anomaly_count += 1
                if score < -0.10:
                    severity = "high"
                elif score < -0.03:
                    severity = "medium"
                else:
                    severity = "low"
                try:
                    from app.core.metrics import anomalies_detected_total
                    anomalies_detected_total.labels(
                        severity=severity, scope=str(row["scope"])
                    ).inc()
                except Exception:  # noqa: BLE001 — metrics must never break inference
                    pass

            records.append({
                "record_id": int(row["id"]),
                "company_id": int(row["company_id"]),
                "scope": str(row["scope"]),
                "category": str(row["category"]),
                "co2_tonnes": float(row["co2_tonnes"]),
                "reporting_year": int(row["reporting_year"]),
                "reporting_month": int(row["reporting_month"]),
                "anomaly_score": round(float(score), 4),
                "is_anomaly": is_anomaly,
                "anomaly_severity": severity,
            })

        total = len(records)
        return {
            "company_id": company_id,
            "year": year,
            "total_records": total,
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_count / total, 4) if total else 0.0,
            "records": records,
        }

    # ── Explainability ───────────────────────────────────────────────────

    def get_feature_importance(self, db: Session, n_top: int = 15) -> dict:
        """Global mean(|SHAP|) feature importance for the forecasting model."""
        model = self._get_forecasting_model()

        df = load_emission_dataframe(db)
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No emission data available to compute feature importance",
            )

        df_features = engineer_forecasting_features(df)
        df_clean = df_features.dropna(subset=["lag_1_month", "lag_12_months"])
        if df_clean.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Not enough historical data to compute feature importance",
            )

        X = df_clean.reindex(columns=get_feature_columns(), fill_value=0).fillna(0)
        importance = get_global_feature_importance(model, X, n_top=n_top)
        return {"feature_importance": importance}


# Module-level singleton — one instance shared across the app
inference_service = EmissionInferenceService()
