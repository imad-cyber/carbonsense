"""
Forecasting: a transparent baseline (champion) and an XGBoost challenger.

Baseline   = same month last year × a trend factor estimated on training data.
Challenger = XGBoost predicting log(this month / same month last year),
             which removes company size from the problem.

The challenger replaces the baseline only if it wins EVERY rolling fold
by a clear margin (see choose_champion).  On smooth synthetic data the
baseline wins; on real data with company-specific trends the challenger
should add value.
"""
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from app.ml.evaluation import SERIES, _scores

SEASONAL_NAIVE = "seasonal_naive"
BASELINE = "seasonal_naive_trend"
CHALLENGER = "xgboost_ratio"

# Clip the log-ratio correction to ±50% to prevent extreme extrapolation
LOG_RATIO_CLIP = 0.5  # ≈ ×0.61 to ×1.65 of last year

METRICS = ("mae", "wape_pct", "median_series_mape_pct", "worst_series_mape_pct")


# ── Feature engineering ───────────────────────────────────────────────────────

def ratio_features(X: pd.DataFrame) -> pd.DataFrame:
    """
    Scale-free features: every value expressed relative to the same month
    last year (lag_12).  This removes the ×100 scale difference across
    series so the model learns relative behaviour, not absolute magnitude.
    """
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


# ── Fitting ───────────────────────────────────────────────────────────────────

def fit_trend_factor(X: pd.DataFrame, y: pd.Series) -> float:
    """
    Median year-over-year ratio across all training rows.
    Robust to outliers; estimated only on training data so there is no leakage.
    """
    ok = (X["lag_12_months"] > 0) & (y > 0)
    return float(np.median(y[ok] / X.loc[ok, "lag_12_months"]))


def fit_challenger(X: pd.DataFrame, y: pd.Series) -> XGBRegressor:
    """
    XGBoost trained to predict log(this month / same month last year).
    Using the log keeps the target symmetric (−0.3 ≈ −26%, +0.3 ≈ +35%).
    Rows where lag_12 is zero or y is zero are dropped: the ratio is undefined.
    """
    ok = (X["lag_12_months"] > 0) & (y > 0)
    model = XGBRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        min_child_weight=10, reg_lambda=5.0,
        random_state=42, n_jobs=-1,
    )
    model.fit(
        ratio_features(X[ok]),
        np.log(y[ok] / X.loc[ok, "lag_12_months"]),
    )
    return model


# ── Prediction ────────────────────────────────────────────────────────────────

def predict_baseline(X: pd.DataFrame, trend_factor: float) -> pd.Series:
    """Baseline: same month last year × the trend factor."""
    return X["lag_12_months"] * trend_factor


def predict_challenger(model: XGBRegressor, X: pd.DataFrame) -> pd.Series:
    """Challenger: multiply last year by the model's log-ratio correction."""
    log_ratio = np.clip(
        model.predict(ratio_features(X)), -LOG_RATIO_CLIP, LOG_RATIO_CLIP
    )
    return pd.Series(X["lag_12_months"].to_numpy() * np.exp(log_ratio), index=X.index)


# ── Evaluation ────────────────────────────────────────────────────────────────

def rolling_origin_compare(
    X: pd.DataFrame,
    y: pd.Series,
    df_features: pd.DataFrame,
    n_folds: int = 4,
    holdout_months: int = 3,
) -> dict:
    """
    Walk-forward (rolling-origin) evaluation.
    Each fold holds out the next `holdout_months` calendar months
    and trains on everything before them.  The folds are non-overlapping
    and step backwards from the most recent data.

    This is the correct way to evaluate a time-series model: the validation
    window is always in the future relative to the training window.
    """
    period = X["reporting_year"] * 12 + X["reporting_month"]
    last = period.max()
    per_fold = []

    for k in range(n_folds):
        end = last - k * holdout_months
        start = end - holdout_months + 1
        val = (period >= start) & (period <= end)
        train = period < start
        if train.sum() == 0 or val.sum() == 0:
            continue
        X_tr, y_tr = X[train], y[train]
        X_va, y_va = X[val], y[val]
        series = df_features.loc[X_va.index, SERIES]

        trend = fit_trend_factor(X_tr, y_tr)
        challenger = fit_challenger(X_tr, y_tr)
        preds = {
            SEASONAL_NAIVE: X_va["lag_12_months"],
            BASELINE: predict_baseline(X_va, trend),
            CHALLENGER: predict_challenger(challenger, X_va),
        }
        per_fold.append({
            "n_train": int(train.sum()),
            "n_val": int(val.sum()),
            "models": {name: _scores(y_va, p, series) for name, p in preds.items()},
        })

    names = (SEASONAL_NAIVE, BASELINE, CHALLENGER)
    mean = {
        n: {
            m: round(float(np.mean([f["models"][n][m] for f in per_fold])), 2)
            for m in METRICS
        }
        for n in names
    }
    return {
        "holdout_months": holdout_months,
        "n_folds": len(per_fold),
        "per_fold": per_fold,
        "mean": mean,
    }


# ── Promotion gate ────────────────────────────────────────────────────────────

def choose_champion(report: dict, margin_pp: float = 0.5) -> str:
    """
    Promote the challenger to champion only if it wins EVERY fold AND
    improves mean WAPE by at least `margin_pp` percentage points.

    Requiring a win on every fold means a single bad fold blocks promotion.
    With four folds, pure random noise would win all four about 1/16 of
    the time, giving a false-positive rate of roughly 6%.
    The margin requirement further guards against noise.
    """
    base = [f["models"][BASELINE]["wape_pct"] for f in report["per_fold"]]
    chal = [f["models"][CHALLENGER]["wape_pct"] for f in report["per_fold"]]
    wins_every_fold = all(c < b for c, b in zip(chal, base))
    mean_gain = float(np.mean(base) - np.mean(chal))
    if wins_every_fold and mean_gain >= margin_pp:
        return CHALLENGER
    return BASELINE
