"""
Trains and registers all CarbonSense models.
Run: python scripts/train_models.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

import mlflow

from app.core.config import settings
from app.db.database import SessionLocal
from app.ml.anomaly_detector import train_anomaly_detector
from app.ml.explainability import get_global_feature_importance
from app.ml.feature_engineering import (
    engineer_forecasting_features,
    load_emission_dataframe,
    prepare_features_and_target,
)
from app.ml.forecaster import (
    BASELINE,
    CHALLENGER,
    choose_champion,
    fit_challenger,
    fit_trend_factor,
    ratio_features,
    rolling_origin_compare,
)
from app.ml.model_registry import save_model


def main() -> None:
    db = SessionLocal()
    try:
        df_raw = load_emission_dataframe(db)
        if df_raw.empty:
            logger.error("No emission data. Run generate_training_data.py first.")
            return
        logger.info("Loaded %d emission records", len(df_raw))

        # ── Forecasting: champion / challenger ────────────────────────────
        logger.info("Engineering features...")
        df_features = engineer_forecasting_features(df_raw)
        X, y = prepare_features_and_target(df_features)
        logger.info("Feature matrix: %s", X.shape)

        logger.info("Running rolling-origin evaluation (%d folds)...", 4)
        report = rolling_origin_compare(X, y, df_features)
        for name, m in report["mean"].items():
            logger.info(
                "mean over %d folds  %-24s WAPE=%.2f%%  worst-series MAPE=%.2f%%",
                report["n_folds"], name, m["wape_pct"], m["worst_series_mape_pct"],
            )

        champion = choose_champion(report, settings.PROMOTION_MARGIN_PP)
        logger.info("Champion: %s", champion)

        # Fit final models on ALL data (no holdout) for deployment
        challenger_model = fit_challenger(X, y)
        trend_factor = fit_trend_factor(X, y)
        importance = get_global_feature_importance(challenger_model, ratio_features(X))

        bundle = {
            "champion": champion,
            "trend_factor": trend_factor,
            "challenger": challenger_model,
            "feature_importance": importance,
            "report": report,
        }

        # Log to MLflow
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
        with mlflow.start_run(run_name="forecasting_champion_challenger") as run:
            mlflow.log_params({
                "champion": champion,
                "promotion_margin_pp": settings.PROMOTION_MARGIN_PP,
                "n_folds": report["n_folds"],
                "holdout_months": report["holdout_months"],
                "trend_factor": round(trend_factor, 4),
            })
            for name, m in report["mean"].items():
                mlflow.log_metric(f"mean_wape_{name}", m["wape_pct"])
            run_id = run.info.run_id

        save_model(
            bundle,
            "forecasting",
            metadata={"mlflow_run_id": run_id, "champion": champion},
        )
        logger.info("✅ Forecasting bundle saved (champion: %s)", champion)

        # ── Anomaly detector ──────────────────────────────────────────────
        logger.info("Training anomaly detector...")
        anomaly_model, scaler, anomaly_run_id = train_anomaly_detector(df_raw)
        save_model(
            {"model": anomaly_model, "scaler": scaler},
            "anomaly_detector",
            metadata={"mlflow_run_id": anomaly_run_id},
        )
        logger.info("✅ Anomaly detector saved")

        logger.info(
            "\n── Training complete ─────────────────────────────────────\n"
            "  Champion         : %s\n"
            "  Trend factor     : %.4f\n"
            "  MLflow UI        : mlflow ui --backend-store-uri sqlite:///mlflow.db",
            champion,
            trend_factor,
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()