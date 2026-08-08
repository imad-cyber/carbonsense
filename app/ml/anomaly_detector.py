import logging
import mlflow
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
import joblib
from app.core.config import settings

logger = logging.getLogger(__name__)

# RobustScaler: scales features using median and IQR instead of mean/std.
# Why Robust over Standard? Emission data has outliers by definition —
# StandardScaler would distort the scale for the majority of normal points.
# RobustScaler is resistant to outliers, which is exactly what we want
# when the TASK is to find outliers.


def build_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Anomaly detection uses different features than forecasting.
    We want to detect records that are unusual relative to:
    - The company's own historical pattern (z-score within company+scope)
    - The expected seasonal pattern for that scope
    - Peer companies in the same sector (future enhancement)
    """
    df = df.copy()

    # Z-score within company+scope group
    # How many standard deviations is this value from the group mean?
    # An anomaly would have a z-score far from 0 (e.g. > 3)
    group = ["company_id", "scope", "category"]

    df["group_mean"] = df.groupby(group)["co2_tonnes"].transform("mean")
    df["group_std"] = df.groupby(group)["co2_tonnes"].transform("std").fillna(1)
    df["z_score"] = (df["co2_tonnes"] - df["group_mean"]) / df["group_std"]

    # Ratio to group median — robust to outliers in the group itself
    df["group_median"] = df.groupby(group)["co2_tonnes"].transform("median")
    df["ratio_to_median"] = df["co2_tonnes"] / df["group_median"].replace(0, 1)

    # Month-over-month change within series
    df = df.sort_values(["company_id", "scope", "category",
                         "reporting_year", "reporting_month"])
    df["mom_change"] = df.groupby(group)["co2_tonnes"].pct_change().fillna(0)

    return df


def train_anomaly_detector(df: pd.DataFrame) -> tuple:
    """
    Trains Isolation Forest for anomaly detection.

    How Isolation Forest works:
    - Builds many random decision trees
    - Anomalies are isolated quickly (fewer splits needed to isolate them)
    - Normal points require many splits to isolate
    - The 'anomaly score' is the average path length across all trees
    - Short path length = anomaly, Long path length = normal

    contamination=0.05 means we expect ~5% of records to be anomalies.
    This threshold determines what score separates normal from anomaly.
    """
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

    df_features = build_anomaly_features(df)

    feature_cols = [
        "co2_tonnes",
        "z_score",
        "ratio_to_median",
        "mom_change",
        "reporting_month",
    ]

    X = df_features[feature_cols].fillna(0)

    # RobustScaler: resistant to the outliers we're trying to detect
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    with mlflow.start_run(run_name="anomaly_detector") as run:
        run_id = run.info.run_id

        model = IsolationForest(
            n_estimators=200,
            contamination=settings.ANOMALY_CONTAMINATION,
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_scaled)

        # Evaluate: what fraction was flagged as anomaly?
        predictions = model.predict(X_scaled)
        anomaly_count = (predictions == -1).sum()
        anomaly_rate = anomaly_count / len(predictions)

        mlflow.log_params({
            "model_type": "IsolationForest",
            "n_estimators": 200,
            "contamination": settings.ANOMALY_CONTAMINATION,
            "n_features": len(feature_cols),
        })
        mlflow.log_metrics({
            "anomaly_count": int(anomaly_count),
            "anomaly_rate": float(anomaly_rate),
            "n_samples": len(X),
        })
        mlflow.set_tags({
            "model_class": "anomaly_detection",
            "framework": "sklearn",
        })

        logger.info(
            f"Anomaly detector trained — "
            f"flagged {anomaly_count} anomalies "
            f"({anomaly_rate:.1%} of {len(X)} records)"
        )

    return model, scaler, run_id