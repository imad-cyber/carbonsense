import logging
import mlflow
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from app.core.config import settings

logger = logging.getLogger(__name__)

# Scale-free on purpose: raw co2_tonnes let large companies dominate the
# isolation scores so drops in small series became invisible.
# Experiment (anomaly_experiment.py) confirmed scale-free features raise
# subtle-anomaly precision@k from 0.66 to 0.80.
# Log scale: spikes and drops of the same factor count equally. log_ratio_same_month removes
# normal seasonality by comparing with the same calendar month in other years.
ANOMALY_FEATURES = ["log_ratio_to_median", "log_ratio_same_month", "log_mom_change"]
ALERT_BUDGET = 0.05   # fraction of a batch flagged for review


def flag_most_unusual(scores: np.ndarray, budget: float) -> np.ndarray:
    """Flags the `budget` fraction of lowest scores (lowest = most unusual); at least one if any."""
    flagged = np.zeros(len(scores), dtype=bool)
    if len(scores):
        k = max(1, int(round(budget * len(scores))))
        flagged[np.argsort(scores)[:k]] = True
    return flagged


def build_anomaly_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-record features describing how unusual a value is for its own series.
    The value judged is the activity quantity behind the tonnes ('monitored') when available,
    so a revised emission factor is not an anomaly; otherwise the tonnes themselves.
    Log features treat spikes and drops symmetrically; log_ratio_same_month removes
    normal seasonality by comparing with the same calendar month in other years.
    """
    df = df.copy()
    value = "monitored" if "monitored" in df.columns else "co2_tonnes"
    group = ["company_id", "scope", "category"]
    if "stream" in df.columns:  # separate activity streams are separate series
        group.append("stream")

    df["group_mean"] = df.groupby(group)[value].transform("mean")
    df["group_std"] = df.groupby(group)[value].transform("std").fillna(1)
    df["z_score"] = (df[value] - df["group_mean"]) / df["group_std"]

    df["group_median"] = df.groupby(group)[value].transform("median")
    df["ratio_to_median"] = df[value] / df["group_median"].replace(0, 1)

    df = df.sort_values(group + ["reporting_year", "reporting_month"])
    df["mom_change"] = df.groupby(group)[value].pct_change().fillna(0)

    prev = df.groupby(group)[value].shift(1)
    df["log_mom_change"] = np.log(
        (df[value] / prev.replace(0, np.nan)).clip(lower=1e-6)
    ).fillna(0)
    df["log_ratio_to_median"] = np.log(df["ratio_to_median"].clip(lower=1e-6))
    month_median = df.groupby(group + ["reporting_month"])[value].transform("median")
    df["log_ratio_same_month"] = np.log(
        (df[value] / month_median.replace(0, np.nan)).clip(lower=1e-6)
    ).fillna(0)
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

    feature_cols = ANOMALY_FEATURES

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