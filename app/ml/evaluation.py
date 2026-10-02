"""
app/ml/evaluation.py — Model evaluation helpers.

Shared scoring utilities for forecasting experiments, anomaly injection,
and multi-seed anomaly benchmarks (see anomaly_benchmark).
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score
from sklearn.preprocessing import RobustScaler

from app.ml.anomaly_detector import build_anomaly_features

SERIES = ["company_id", "scope", "category"]

# Spike and drop multiplier ranges by severity.
# "subtle" sits inside normal seasonal swings, so it is deliberately hard to detect.
SEVERITY = {
    "obvious": ((2.5, 4.0), (0.15, 0.40)),
    "subtle": ((1.4, 1.8), (0.55, 0.75)),
}


def _scores(y_true: pd.Series, y_pred: pd.Series, series: pd.DataFrame) -> dict:
    """
    MAE:  average absolute error in tonnes (scale-dependent).
    WAPE: sum(|error|) / sum(|actual|) × 100 — a pooled percentage where large
          and small series contribute in proportion to their volume.
    MAPE per series, then median and worst — shows whether any single series is
    badly predicted while the pooled WAPE looks fine.
    """
    err = (y_true - y_pred).abs()
    ape = err / y_true.replace(0, np.nan)
    per_series = ape.groupby([series[c] for c in SERIES]).mean()
    return {
        "mae": round(float(err.mean()), 1),
        "wape_pct": round(float(err.sum() / y_true.abs().sum() * 100), 2),
        "median_series_mape_pct": round(float(per_series.median() * 100), 2),
        "worst_series_mape_pct": round(float(per_series.max() * 100), 2),
    }


def inject_anomalies(
    df: pd.DataFrame, rate: float, severity: str, seed: int = 42
) -> pd.DataFrame:
    """
    Return a copy of df with known anomalies injected at random positions.
    Each injected record is either a spike (value × large factor) or a drop
    (value × small factor < 1). A 'kind' column records what was planted.

    Using a fixed seed makes the evaluation reproducible across runs.
    """
    (s_lo, s_hi), (d_lo, d_hi) = SEVERITY[severity]
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    out["kind"] = "none"
    n_inject = int(len(out) * rate)
    for i in rng.choice(len(out), size=n_inject, replace=False):
        spike = rng.random() < 0.5
        factor = rng.uniform(s_lo, s_hi) if spike else rng.uniform(d_lo, d_hi)
        out.loc[i, "co2_tonnes"] *= factor
        out.loc[i, "kind"] = "spike" if spike else "drop"
    return out


CURRENT_FEATURES = ["co2_tonnes", "z_score", "ratio_to_median", "mom_change", "reporting_month"]
SCALE_FREE_FEATURES = ["z_score", "ratio_to_median", "mom_change", "reporting_month"]


def _iso_rank(feats: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Higher = more anomalous."""
    X = RobustScaler().fit_transform(feats[cols].fillna(0))
    iso = IsolationForest(n_estimators=200, random_state=42, n_jobs=-1).fit(X)
    return -iso.score_samples(X)


def anomaly_benchmark(
    df: pd.DataFrame,
    rates=(0.02, 0.05),
    severities=("obvious", "subtle"),
    seeds=range(10),
) -> pd.DataFrame:
    """
    Rank all records by suspiciousness and check how many planted anomalies
    land in the top k (k = number planted). One row per (setting, seed, scorer).
    """
    rows = []
    for severity in severities:
        for rate in rates:
            for seed in seeds:
                feats = build_anomaly_features(
                    inject_anomalies(df, rate, severity, seed)
                ).sort_index()
                kind = feats["kind"].to_numpy()
                truth = kind != "none"
                k = int(truth.sum())
                log_ratio = np.abs(
                    np.log(feats["ratio_to_median"].clip(lower=1e-6))
                ).to_numpy()
                scorers = {
                    "iso_current_features": _iso_rank(feats, CURRENT_FEATURES),
                    "iso_scale_free": _iso_rank(feats, SCALE_FREE_FEATURES),
                    "abs_zscore": feats["z_score"].abs().to_numpy(),
                    "abs_log_ratio_to_median": log_ratio,
                }
                for name, s in scorers.items():
                    top = np.argsort(-s)[:k]
                    in_top = np.zeros(len(s), dtype=bool)
                    in_top[top] = True
                    spikes, drops = kind == "spike", kind == "drop"
                    rows.append({
                        "severity": severity, "rate": rate, "seed": seed, "scorer": name,
                        "precision_at_k": float(truth[top].mean()),
                        "avg_precision": float(average_precision_score(truth, s)),
                        "spikes_found": float(in_top[spikes].mean()) if spikes.any() else np.nan,
                        "drops_found": float(in_top[drops].mean()) if drops.any() else np.nan,
                    })
    return pd.DataFrame(rows)
