"""
Trains all CarbonSense ML models and saves them to disk.
Run: python scripts/train_models.py

This script is also what the Celery retraining task calls in production.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

from app.db.database import SessionLocal
from app.ml.feature_engineering import (
    load_emission_dataframe,
    engineer_forecasting_features,
    prepare_features_and_target,
)
from app.ml.forecasting_model import train_with_mlflow
from app.ml.anomaly_detector import train_anomaly_detector
from app.ml.model_registry import save_model
from app.core.config import settings


def main():
    db = SessionLocal()

    try:
        logger.info("Loading emission data from database...")
        df_raw = load_emission_dataframe(db)

        if df_raw.empty:
            logger.error("No emission data found. Run generate_training_data.py first.")
            return

        logger.info(f"Loaded {len(df_raw)} emission records")

        # ── Train forecasting model ──────────────────────────────────────
        logger.info("Engineering features for forecasting model...")
        df_features = engineer_forecasting_features(df_raw)
        X, y = prepare_features_and_target(df_features)

        logger.info(f"Feature matrix shape: {X.shape}")
        logger.info("Training XGBoost forecasting model...")

        forecasting_model, metrics, run_id = train_with_mlflow(X, y)

        # Quality gate: only save if model meets minimum R²
        if metrics["val_r2"] < settings.MIN_FORECAST_R2:
            logger.error(
                f"Model quality gate FAILED: "
                f"R²={metrics['val_r2']:.3f} < "
                f"threshold={settings.MIN_FORECAST_R2}. "
                f"Model NOT saved."
            )
        else:
            save_model(
                forecasting_model,
                "forecasting",
                metadata={
                    "mlflow_run_id": run_id,
                    "val_r2": metrics["val_r2"],
                    "val_mae": metrics["val_mae"],
                    "feature_columns": X.columns.tolist(),
                },
            )
            logger.info(
                f"✅ Forecasting model saved — "
                f"R²={metrics['val_r2']:.3f}, "
                f"MAE={metrics['val_mae']:.1f}t CO₂e"
            )

        # ── Train anomaly detector ───────────────────────────────────────
        logger.info("Training anomaly detection model...")
        anomaly_model, scaler, anomaly_run_id = train_anomaly_detector(df_raw)

        save_model(
            {"model": anomaly_model, "scaler": scaler},
            "anomaly_detector",
            metadata={"mlflow_run_id": anomaly_run_id},
        )
        logger.info("✅ Anomaly detector saved")

        logger.info("\n── Training complete ──────────────────────────────────")
        logger.info(f"Forecasting  R²  : {metrics['val_r2']:.3f}")
        logger.info(f"Forecasting  MAE : {metrics['val_mae']:.1f} t CO₂e")
        logger.info(f"MLflow UI        : mlflow ui --backend-store-uri sqlite:///mlflow.db")

    finally:
        db.close()


if __name__ == "__main__":
    main()