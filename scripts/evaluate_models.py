"""
Writes docs/MODEL_CARD.md from the model that is actually served, a multi-seed anomaly
benchmark and a check on the demo company.
Run after train_models.py:   python scripts/evaluate_models.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from pathlib import Path

import pandas as pd

from app.db.database import SessionLocal
from app.ml.evaluation import anomaly_benchmark
from app.ml.feature_engineering import load_emission_dataframe
from app.ml.findings import group_findings
from app.ml.forecaster import BASELINE, CHALLENGER, SEASONAL_NAIVE
from app.ml.inference import inference_service
from app.ml.model_registry import load_model
from app.models.company import Company

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEMO_COMPANY = "Démo Industrie SA (synthetic activity data)"  # same name as in seed_demo_company.py

MODEL_LABELS = {
    SEASONAL_NAIVE: "Same month last year",
    BASELINE: "Same month last year x trend factor",
    CHALLENGER: "XGBoost on log-ratio to last year",
}
SCORER_LABELS = {
    "iso_current_features": "Isolation Forest, raw tonnes included",
    "iso_scale_free": "Isolation Forest, scale-free features (previous)",
    "iso_log_features": "Isolation Forest, log-ratio features (served)",
    "abs_zscore": "abs(z-score) within series",
    "abs_log_ratio_to_median": "abs(log(value / series median))",
    "abs_log_ratio_same_month": "abs(log(value / same-calendar-month median))",
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
    return "\n".join([
        "## Forecasting",
        "",
        f"Served model: **{MODEL_LABELS[bundle['champion']]}**. Trend factor: {bundle['trend_factor']:.4f}.",
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
    ])


def anomaly_section(bench: pd.DataFrame) -> str:
    agg = (
        bench.groupby(["severity", "rate", "scorer"])
        .agg(
            p_mean=("precision_at_k", "mean"),
            p_std=("precision_at_k", "std"),
            spikes_found=("spikes_found", "mean"),
            drops_found=("drops_found", "mean"),
            known_found=("known_found", "mean"),
        )
        .reset_index()
    )
    rows = [
        f"| {r.severity} | {r.rate:.0%} | {SCORER_LABELS[r.scorer]} | "
        f"{r.p_mean:.3f} +/- {r.p_std:.3f} | {r.spikes_found:.2f} | {r.drops_found:.2f} | {r.known_found:.2f} |"
        for r in agg.itertuples()
    ]
    return "\n".join([
        "## Anomaly detection",
        "",
        "Anomalies were planted by multiplying random records up (spikes) or down (drops); "
        "the demo company's known planted records count as positives too. Each scorer ranks "
        "every record by suspiciousness; precision@k is the share of the top k that are "
        f"positives, with k = number of positives. Mean +/- std over {bench['seed'].nunique()} seeds.",
        "",
        "| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found | Demo planted found |",
        "|---|---|---|---|---|---|---|",
        *rows,
    ])


def demo_section(df_raw: pd.DataFrame, demo_id: int | None) -> str:
    if demo_id is None:
        return "## Demo company check\n\nNo demo company found (run scripts/seed_demo_company.py)."
    rows = df_raw[df_raw["company_id"] == demo_id]
    records = [{**r, "record_id": r["id"]} for r in rows.to_dict("records")]
    findings = group_findings(inference_service.detect_anomalies(records))
    known_ids = set(rows.loc[rows["known_anomaly"], "id"])
    hit = [f for f in findings if any(r["record_id"] in known_ids for r in f["records"])]
    activities = rows["activity_group_id"].nunique()
    planted = rows.loc[rows["known_anomaly"], "activity_group_id"].nunique()
    return "\n".join([
        "## Demo company check",
        "",
        f"The served detector, run over the demo company's {activities} activity entries "
        f"(2022-2024), produced {len(findings)} findings. It found {len(hit)} of the {planted} planted "
        f"anomalies; the other {len(findings) - len(hit)} findings are not planted (false alarms or "
        "genuine extremes; the data has no other labelled errors). Three planted anomalies make "
        "this an illustration, not a benchmark.",
    ])


LIMITATIONS = """## Limitations
- All data is synthetic. Five companies come from `scripts/generate_training_data.py`: tonnes entered directly, smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. One demo company comes from `scripts/seed_demo_company.py`: synthetic activity quantities converted with real ADEME Base Carbone V23.6 factors. Recovering the built-in trend factor only confirms what the generators put in.
- Three anomalies in the demo company were planted by the author (seven records, because each activity creates several). The benchmark counts them as known positives. Finding them illustrates the detector and does not benchmark it.
- Benchmark anomalies are planted by multiplication, which favours log-ratio scorers. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- The served detector measures each record against the same calendar month in other years and against the series median, on log scales so that spikes and drops count equally. With three years of history each same-month reference is the median of only three values: it is noisy, and two anomalies in the same month would hide each other.
- Flags are a review queue: the most unusual 5% of a company's records are flagged whatever the data quality, so a clean company still gets flags. They show where to look first and are not confirmed errors.
- Anomalies are judged on the activity quantity behind each record (tonnes divided by the emission factor), so a revised factor does not raise one. A stream whose factor unit changes (for example kWh PCI to kWh PCS) is not comparable across the change.
- The high, medium and low labels come from a fixed rule on the ratio to the same calendar month's median in other years (at least 2x or at most 0.5x for high). With three years of data that reference is the median of three values. The planted anomalies (2x, 2.6x and 0.3x) sit at or beyond the high threshold, so finding them says little about the severity rule.
- Each benchmark run plants only about 2% or 5% of records; differences smaller than the reported spread are not meaningful.
- The forecast evaluation window contains the demo company's planted anomalies (June 2024 electricity, and February 2024 gas through its "same month last year" value). They produce the largest errors and drive the worst-series MAPE; the median series MAPE in the table above is not affected.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data. The Scope 1 and 2 accounting lines of one published filing were reproduced (docs/VALIDATION_BEGES.md); that validates the arithmetic and allocation policy for those lines, not the models."""


def main() -> None:
    db = SessionLocal()
    try:
        df_raw = load_emission_dataframe(db)
        demo_id = db.query(Company.id).filter(Company.name == DEMO_COMPANY).scalar()
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
        demo_section(df_raw, demo_id),
        LIMITATIONS,
    ])
    Path("docs").mkdir(exist_ok=True)
    Path("docs/MODEL_CARD.md").write_text(card, encoding="utf-8")
    logger.info("Wrote docs/MODEL_CARD.md")


if __name__ == "__main__":
    main()
