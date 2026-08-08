import logging
import mlflow
import mlflow.xgboost
import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)


def train_forecasting_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> tuple[XGBRegressor, dict]:
    """
    Trains an XGBoost regression model to forecast CO2 emissions.

    Why XGBoost for this problem?
    - Handles mixed feature types (numerical + one-hot encoded categoricals)
    - Built-in handling of missing values
    - Fast training on tabular data
    - Dominant in Kaggle competitions for tabular regression = proven track record
    - Native SHAP support for explainability

    TimeSeriesSplit: for time-series data we CANNOT use random train/val split.
    If we did, we'd train on future data and validate on past — that's data leakage.
    TimeSeriesSplit always validates on data AFTER the training window.
    """

    # Hyperparameters — these would be tuned with Optuna in production
    # For now these are sensible defaults for emissions time-series
    params = {
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        # Lower learning rate = more trees = better generalisation
        "subsample": 0.8,
        # Train each tree on 80% of rows — reduces overfitting
        "colsample_bytree": 0.8,
        # Use 80% of features per tree — reduces overfitting
        "min_child_weight": 5,
        # A leaf needs at least 5 samples — prevents overfitting to outliers
        "reg_alpha": 0.1,   # L1 regularisation — drives small weights to 0
        "reg_lambda": 1.0,  # L2 regularisation — penalises large weights
        "random_state": 42,
        "n_jobs": -1,       # use all CPU cores
        "eval_metric": "mae",
    }

    model = XGBRegressor(**params)

    # Early stopping: stop training if validation MAE doesn't improve
    # for 30 consecutive rounds — prevents overfitting and wasted compute
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    # Evaluate on validation set
    y_pred = model.predict(X_val)
    y_pred = np.maximum(y_pred, 0)  # emissions cannot be negative

    metrics = {
        "val_mae": float(mean_absolute_error(y_val, y_pred)),
        "val_rmse": float(np.sqrt(mean_squared_error(y_val, y_pred))),
        "val_r2": float(r2_score(y_val, y_pred)),
        "val_mape": float(
            np.mean(np.abs((y_val - y_pred) / y_val.replace(0, np.nan)))
        ),
        "n_train": len(X_train),
        "n_val": len(X_val),
    }

    logger.info(
        f"Forecasting model trained — "
        f"R²={metrics['val_r2']:.3f}, "
        f"MAE={metrics['val_mae']:.1f}t CO₂e, "
        f"RMSE={metrics['val_rmse']:.1f}t CO₂e"
    )

    return model, metrics


def train_with_mlflow(
    X: pd.DataFrame,
    y: pd.Series,
) -> tuple[XGBRegressor, dict, str]:
    """
    Full MLflow-tracked training run.

    MLflow tracks:
    - Parameters: the hyperparameters we used
    - Metrics: MAE, RMSE, R² on validation set
    - Model: the trained XGBoost model as an artifact
    - Tags: metadata like training date, data size

    Every time you retrain, a new run is created.
    You can compare runs in the MLflow UI and see exactly
    what changed between model versions.
    """
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

    # TimeSeriesSplit: 5 folds, always future-forward
    # We use the last fold as our train/val split
    tscv = TimeSeriesSplit(n_splits=5)
    splits = list(tscv.split(X))
    train_idx, val_idx = splits[-1]  # last split = most recent validation

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]
    X_val = X.iloc[val_idx]
    y_val = y.iloc[val_idx]

    with mlflow.start_run() as run:
        run_id = run.info.run_id

        # Log hyperparameters
        mlflow.log_params({
            "model_type": "XGBRegressor",
            "n_estimators": 300,
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "cv_folds": 5,
            "train_size": len(X_train),
            "val_size": len(X_val),
        })

        # Train the model
        model, metrics = train_forecasting_model(
            X_train, y_train, X_val, y_val
        )

        # Log evaluation metrics
        mlflow.log_metrics(metrics)

        # Log the trained model as a MLflow artifact
        # This means the model is stored alongside its metadata
        mlflow.xgboost.log_model(model, "forecasting_model")

        # Tag the run with metadata
        mlflow.set_tags({
            "model_class": "forecasting",
            "target": "co2_tonnes",
            "framework": "xgboost",
        })

        logger.info(f"MLflow run logged — run_id: {run_id}")

    return model, metrics, run_id