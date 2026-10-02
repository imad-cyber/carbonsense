"""
Writes docs/MODEL_CARD.md from the model that is actually served
plus a multi-seed anomaly benchmark.
Run: python scripts/evaluate_models.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from pathlib import Path

import pandas as pd

from app.db.database import SessionLocal
from app.ml.evaluation import anomaly_benchmark
from app.ml.feature_engineering import load_emission_dataframe
from app.ml.forecaster import BASELINE, CHALLENGER, SEASONAL_NAIVE
from app.ml.model_registry import load_model

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MODEL_LABELS = {
    SEASONAL_NAIVE: "Same month last year",
    BASELINE: "Same month last year x trend factor",
    CHALLENGER: "XGBoost on log-ratio to last year",
}
SCORER_LABELS = {
    "iso_current_features": "Isolation Forest, raw tonnes included",
    "iso_scale_free": "Isolation Forest, scale-free features",
    "abs_zscore": "|z-score| within series",
    "abs_log_ratio_to_median": "|log(value / series median)|",
}


def forecasting_section(bundle: dict) -> str:
    report = bundle["report"]
    mean_rows = [
        f"| {MODEL_LABELS[name]} | {m['mae']:,} | {m['wape_pct']} | "
        f"{m['median_series_mape_pct']} | {m['worst_series_mape_pct']} |"
        for name, m in report["mean"].items()
    ]
    fold_rows = [
        f"| {i + 1} | {f['models'][BASELINE]['wape_pct']} | {f['models'][CHALLENGER]['wape_pct']} |"
        for i, f in enumerate(report["per_fold"])
    ]
    lines = [
        "## Forecasting",
        "",
        f"Served model: **{MODEL_LABELS[bundle['champion']]}**. "
        f"Trend factor: {bundle['trend_factor']:.4f}.",
        "",
        f"Walk-forward evaluation: {report['n_folds']} folds, each trained on the past and "
        f"scored on the next {report['holdout_months']} months of every series. "
        "The challenger replaces the baseline only if it wins every fold and improves mean WAPE "
        "by at least 0.5 percentage points. Differences smaller than that are within "
        "fold-to-fold noise.",
        "",
        "Mean over folds:",
        "",
        "| Method | MAE (t CO2e) | WAPE % | Median series MAPE % | Worst series MAPE % |",
        "|---|---|---|---|---|",
        *mean_rows,
        "",
        "WAPE per fold (1 = most recent):",
        "",
        "| Fold | Baseline | Challenger |",
        "|---|---|---|",
        *fold_rows,
    ]
    return "\n".join(lines)


def anomaly_section(bench: pd.DataFrame) -> str:
    agg = (
        bench.groupby(["severity", "rate", "scorer"])
        .agg(
            p_mean=("precision_at_k", "mean"),
            p_std=("precision_at_k", "std"),
            spikes_found=("spikes_found", "mean"),
            drops_found=("drops_found", "mean"),
        )
        .reset_index()
    )
    rows = [
        f"| {r.severity} | {r.rate:.0%} | {SCORER_LABELS[r.scorer]} | "
        f"{r.p_mean:.3f} +/- {r.p_std:.3f} | {r.spikes_found:.2f} | {r.drops_found:.2f} |"
        for r in agg.itertuples()
    ]
    n_seeds = bench["seed"].nunique()
    lines = [
        "## Anomaly detection",
        "",
        "Anomalies were planted by multiplying random records up (spikes) or down (drops). "
        "Each scorer ranks every record by suspiciousness; precision@k is the share of the "
        f"top k that are planted anomalies, with k = number planted. Mean +/- std over {n_seeds} seeds. "
        "The served detector is the scale-free Isolation Forest.",
        "",
        "| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found |",
        "|---|---|---|---|---|---|",
        *rows,
    ]
    return "\n".join(lines)


LIMITATIONS = """## Limitations
- All data is synthetic, from `scripts/generate_training_data.py`: smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. A forecaster cannot be shown to beat a baseline on data this regular, and recovering the trend factor only confirms the built-in decline.
- Anomalies are planted by multiplication, so ranking by distance from the series median scores near-perfectly by construction. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- The detector compares each record with the series median, not with the same calendar month, so seasonal peaks look mildly unusual.
- Each run plants only about 28 to 72 anomalies; differences smaller than the reported spread are not meaningful.
- Production flags use an assumed 5% contamination rate, so about 5% of records are flagged whatever the data quality. The benchmark ranks records and does not use that threshold.
- Severity labels (high, medium, low) come from a simple rule on the deviation from the series median, not from a calibrated model.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data."""


def main() -> None:
    db = SessionLocal()
    try:
        df_raw = load_emission_dataframe(db)
    finally:
        db.close()

    payload = load_model("forecasting")
    if payload is None or df_raw.empty:
        logger.error("Need data and a trained model. Run generate_training_data.py and train_models.py.")
        return

    bench = anomaly_benchmark(df_raw)

    card = "\n\n".join([
        "# CarbonSense Model Card",
        f"Model trained: {payload.get('saved_at', 'unknown')}",
        "## Data\n"
        f"{len(df_raw)} monthly emission records. Sources: "
        f"{', '.join(sorted(df_raw['data_source'].unique()))}.\n\n"
        "**All results below are on synthetic data.** They show the pipeline works end to end, "
        "not that the models predict real company emissions.",
        forecasting_section(payload["model"]),
        anomaly_section(bench),
        LIMITATIONS,
    ])

    Path("docs").mkdir(exist_ok=True)
    Path("docs/MODEL_CARD.md").write_text(card, encoding="utf-8")
    logger.info("Wrote docs/MODEL_CARD.md")


if __name__ == "__main__":
    main()
