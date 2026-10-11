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

from app.ml.feature_engineering import (
    engineer_forecasting_features,
    get_feature_columns,
)
from app.ml.anomaly_detector import (
    ALERT_BUDGET, ANOMALY_FEATURES, build_anomaly_features, flag_most_unusual,
)
from app.ml.explainability import explain_prediction
from app.ml.forecaster import CHALLENGER, predict_baseline, predict_challenger, ratio_features
from app.ml.model_registry import load_model, model_exists

logger = logging.getLogger(__name__)


def _severity(ratio: float) -> str:
    """Transparent rule based on size of deviation from the series median."""
    if ratio >= 2.0 or ratio <= 0.5:
        return "high"
    if ratio >= 1.5 or ratio <= 0.67:
        return "medium"
    return "low"  # flagged for its pattern, not its size


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

    # ── Model loading ─────────────────────────────────────────────────────

    def _load_forecasting(self) -> dict:
        """Return the full forecasting bundle (champion, trend_factor, challenger, …)."""
        if self._forecasting_payload is None:
            self._forecasting_payload = load_model("forecasting")
        if self._forecasting_payload is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Forecasting model not trained yet — run scripts/train_models.py",
            )
        return self._forecasting_payload["model"]

    def _load_anomaly(self):
        """Return (IsolationForest, RobustScaler)."""
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

    # ── Forecasting ───────────────────────────────────────────────────────

    def predict_emissions(
        self,
        company_id: int,
        scope: str,
        category: str,
        reporting_year: int,
        reporting_month: int,
        recent_records: list[dict],
    ) -> dict:
        """
        Forecast CO2 emissions for one company/scope/category/month.

        Returns both the baseline forecast and the challenger forecast so the
        caller can see when they disagree.  The model_used field says which one
        is the current champion.

        Accepts pre-fetched records so the method is DB-free and testable.
        Only the month immediately after the latest data is supported.
        """
        bundle = self._load_forecasting()

        # Filter to the requested series
        series = [
            r for r in recent_records
            if r["company_id"] == company_id
            and r["scope"] == scope
            and r["category"] == category
        ]
        if len(series) < 13:
            raise ValueError(
                f"Need at least 13 months of history for {scope}/{category}; "
                f"found {len(series)}."
            )

        # Validate that only the next sequential month is requested
        last = max(series, key=lambda r: (r["reporting_year"], r["reporting_month"]))
        nxt = last["reporting_year"] * 12 + (last["reporting_month"] - 1) + 1
        expected = (nxt // 12, nxt % 12 + 1)
        if (reporting_year, reporting_month) != expected:
            raise ValueError(
                f"Forecast supports only the next month after the latest data: "
                f"{expected[0]}-{expected[1]:02d}."
            )

        target = {
            "company_id": company_id, "scope": scope, "category": category,
            "co2_tonnes": 0.0,  # placeholder; features no longer read it
            "reporting_year": reporting_year, "reporting_month": reporting_month,
        }
        df_features = engineer_forecasting_features(pd.DataFrame(series + [target]))
        mask = (
            (df_features["reporting_year"] == reporting_year)
            & (df_features["reporting_month"] == reporting_month)
        )
        X_raw = df_features[mask].tail(1).reindex(columns=get_feature_columns(), fill_value=0)

        lag12 = float(X_raw["lag_12_months"].iloc[0])
        baseline_val = float(predict_baseline(X_raw, bundle["trend_factor"]).iloc[0])
        challenger_val = float(predict_challenger(bundle["challenger"], X_raw).iloc[0])
        champion = bundle["champion"]
        served = challenger_val if champion == CHALLENGER else baseline_val

        return {
            "company_id": company_id,
            "scope": scope,
            "category": category,
            "reporting_year": reporting_year,
            "reporting_month": reporting_month,
            "predicted_co2_tonnes": round(max(served, 0.0), 2),
            "model_used": champion,
            "models_disagree": abs(challenger_val - baseline_val) / max(baseline_val, 1e-9) > 0.15,
            "baseline": {
                "method": "same month last year x trend factor",
                "same_month_last_year": round(lag12, 2),
                "trend_factor": round(bundle["trend_factor"], 4),
                "forecast": round(baseline_val, 2),
            },
            "challenger": {
                "forecast": round(challenger_val, 2),
                "shap_on_log_ratio_to_last_year": explain_prediction(
                    bundle["challenger"], ratio_features(X_raw)
                ),
            },
        }

    # ── Anomaly detection ─────────────────────────────────────────────────

    def detect_anomalies(
        self, records: list[dict], alert_budget: float | None = ALERT_BUDGET
    ) -> list[dict]:
        """
        Scores records and flags the most unusual ones.
        alert_budget: fraction of the batch to flag, a review queue. Flags show where to look
        first, not confirmed errors; a clean batch still gets its top records flagged.
        None falls back to the model's own training-time threshold.
        """
        model, scaler = self._load_anomaly()

        df = pd.DataFrame(records)
        # build_anomaly_features sorts rows; restore input order so scores line up with `records`
        df_features = build_anomaly_features(df).sort_index()
        X_scaled = scaler.transform(df_features[ANOMALY_FEATURES].fillna(0))

        scores = model.score_samples(X_scaled)
        flagged = (
            flag_most_unusual(scores, alert_budget) if alert_budget is not None
            else model.predict(X_scaled) == -1
        )
        same_month = np.exp(df_features["log_ratio_same_month"].to_numpy())
        series = df_features["ratio_to_median"].to_numpy()

        results = []
        for i, record in enumerate(records):
            results.append({
                **record,
                "anomaly_score": round(float(scores[i]), 4),
                "is_anomaly": bool(flagged[i]),
                # severity rule (2x / 0.5x = high) applied to the same-month ratio
                "anomaly_severity": _severity(float(same_month[i])) if flagged[i] else None,
                "times_same_month": round(float(same_month[i]), 2),
                "times_series_median": round(float(series[i]), 2),
            })
        return results

    # ── Explainability ────────────────────────────────────────────────────

    def get_feature_importance(self) -> list[dict]:
        """
        Mean |SHAP| of the challenger model, pre-computed at train time.

        Returning pre-computed importance avoids the old bug of computing SHAP
        on an all-zeros frame (which made every feature look equally unimportant).
        """
        bundle = self._load_forecasting()
        return bundle.get("feature_importance", [])


# Module-level singleton — one instance shared across the app
inference_service = EmissionInferenceService()
