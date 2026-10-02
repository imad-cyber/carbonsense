"""
Can a scale-free, ratio-target model beat seasonal naive?
Run: python scripts/forecast_experiment.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.db.database import SessionLocal
from app.ml.evaluation import SERIES, _scores
from app.ml.feature_engineering import (
    engineer_forecasting_features,
    load_emission_dataframe,
    prepare_features_and_target,
)
from app.ml.forecasting_model import train_forecasting_model


def ratio_features(X: pd.DataFrame) -> pd.DataFrame:
    """Scale-free features: everything relative to the same month last year."""
    base = X["lag_12_months"].replace(0, np.nan)
    out = pd.DataFrame(index=X.index)
    out["lag1_ratio"] = X["lag_1_month"] / base
    out["roll3_ratio"] = X["rolling_mean_3m"] / base
    out["volatility"] = X["rolling_std_12m"] / X["rolling_mean_3m"].replace(0, np.nan)
    for col in ("yoy_change", "month_sin", "month_cos", "quarter"):
        out[col] = X[col]
    for col in X.columns:
        if col.startswith(("scope_", "cat_")):
            out[col] = X[col]
    return out.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)


def fit_ratio_model(X: pd.DataFrame, y: pd.Series) -> XGBRegressor:
    model = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        min_child_weight=10, reg_lambda=5.0,
        random_state=42, n_jobs=-1,
    )
    # Target: log(this month / same month last year)
    model.fit(ratio_features(X), np.log(y / X["lag_12_months"]))
    return model


def predict_ratio(model: XGBRegressor, X: pd.DataFrame) -> pd.Series:
    log_ratio = np.clip(model.predict(ratio_features(X)), -0.5, 0.5)
    return pd.Series(X["lag_12_months"].to_numpy() * np.exp(log_ratio), index=X.index)


def main() -> None:
    db = SessionLocal()
    try:
        df_raw = load_emission_dataframe(db)
    finally:
        db.close()

    df_features = engineer_forecasting_features(df_raw)
    X, y = prepare_features_and_target(df_features)
    period = X["reporting_year"] * 12 + X["reporting_month"]
    last = period.max()

    rows = []
    for back in (0, 6):  # two rolling-origin folds
        val = (period > last - back - 6) & (period <= last - back)
        train = period <= last - back - 6
        X_tr, y_tr, X_va, y_va = X[train], y[train], X[val], y[val]
        series = df_features.loc[X_va.index, SERIES]

        # Bias correction estimated on the training window only
        bias = float(np.median(y_tr / X_tr["lag_12_months"]))
        raw_model, _ = train_forecasting_model(X_tr, y_tr, X_va, y_va)

        preds = {
            "seasonal_naive": X_va["lag_12_months"],
            "seasonal_naive_x_bias": X_va["lag_12_months"] * bias,
            "xgboost_raw (current)": pd.Series(
                np.maximum(raw_model.predict(X_va), 0), index=X_va.index
            ),
            "xgboost_ratio (new)": predict_ratio(fit_ratio_model(X_tr, y_tr), X_va),
        }
        for name, pred in preds.items():
            rows.append({
                "fold": f"holdout ending -{back}m", "model": name,
                "n_train": len(X_tr), **_scores(y_va, pred, series),
            })

    result = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    print("\nMean WAPE across folds:")
    print(result.groupby("model")["wape_pct"].mean().sort_values().round(2))


if __name__ == "__main__":
    main()
