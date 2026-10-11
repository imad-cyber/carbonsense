import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.models.emission import EmissionRecord


def stream_key(
    emission_factor_id: int | None,
    factor_post_type: str | None,
    activity_label: str | None = None,
) -> str:
    """
    Records of one monitored stream (e.g. boiler gas at site A) form one series for anomaly
    scoring. An explicit activity_label identifies the stream and survives a change of
    emission factor (factors are versioned yearly). Without a label the factor id is used, so a
    new factor starts a new series. Direct-input records are one stream.
    """
    post = factor_post_type or "total"
    if activity_label:
        return f"{activity_label.strip().lower()}:{post}"
    if not emission_factor_id:
        return "direct"
    return f"{emission_factor_id}:{post}"


def _require_contiguous_months(df: pd.DataFrame) -> None:
    period = df["reporting_year"] * 12 + df["reporting_month"]
    span = period.groupby([df[c] for c in ("company_id", "scope", "category")]).agg(
        ["min", "max", "nunique"]
    )
    gapped = span[(span["max"] - span["min"] + 1) != span["nunique"]]
    if not gapped.empty:
        raise ValueError(
            f"Monthly gaps in {len(gapped)} series (e.g. {list(gapped.index[:3])}); "
            "lag features need consecutive months."
        )

def monitored_value(co2_tonnes: float, factor_kg_co2e_per_unit: float | None) -> float:
    """
    The activity quantity (in the factor's unit) behind a record: tonnes x 1000 / factor.
    Anomalies are judged on this, so a revised emission factor does not look like one.
    Direct-input records have no factor, so their tonnes are used as they are.
    """
    if factor_kg_co2e_per_unit:
        return co2_tonnes * 1000.0 / factor_kg_co2e_per_unit
    return co2_tonnes


def load_emission_dataframe(db: Session, company_id: int = None) -> pd.DataFrame:
    """
    Loads emission records from PostgreSQL into a pandas DataFrame.
    Why pandas? It's the universal intermediate format between
    SQL databases and ML libraries — every data science team uses this.
    """
    query = db.query(EmissionRecord)
    if company_id:
        query = query.filter(EmissionRecord.company_id == company_id)

    records = query.all()

    if not records:
        return pd.DataFrame()

    data = [
        {
            "id": r.id,
            "company_id": r.company_id,
            "scope": r.scope.value,
            "category": r.category.value,
            "co2_tonnes": r.co2_tonnes,
            "reporting_year": r.reporting_year,
            "reporting_month": r.reporting_month or 0,
            "data_source": r.data_source or "unknown",
            "known_anomaly": (r.notes or "").startswith("DEMO planted"),
            "monitored": monitored_value(r.co2_tonnes, r.factor_kg_co2e_per_unit),
            "stream": stream_key(r.emission_factor_id, r.factor_post_type, r.activity_label),
            "activity_group_id": r.activity_group_id,
        }
        for r in records
    ]

    return pd.DataFrame(data)


def engineer_forecasting_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transforms raw emission records into features for the forecasting model.

    Feature engineering is the most impactful step in tabular ML.
    The choices here directly determine model performance.
    Good features encode domain knowledge — e.g. 'winter months have
    higher Scope 1 emissions' becomes a sine/cosine time feature.
    """

    if df.empty:
        return df

    # One row per series and month. Lags and rolling windows below assume it.
    df = df[df["reporting_month"].between(1, 12)]   # annual records are not monthly data
    if df.empty:
        return df
    df = df.groupby(
        ["company_id", "scope", "category", "reporting_year", "reporting_month"],
        as_index=False,
    )["co2_tonnes"].sum()
    _require_contiguous_months(df)

    df = df.copy()

    # ── Temporal features ────────────────────────────────────────────────
    # Cyclical encoding: month 12 and month 1 are close in time,
    # but 12 and 1 are far apart numerically. Sine/cosine encoding
    # places them close together in feature space — the model learns
    # the circular nature of months without being told explicitly.
    df["month_sin"] = np.sin(2 * np.pi * df["reporting_month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["reporting_month"] / 12)

    # Year offset — linear trend feature
    # 2022 → 0, 2023 → 1, 2024 → 2
    df["year_offset"] = df["reporting_year"] - df["reporting_year"].min()

    # Quarter — regulatory reporting often uses quarterly aggregation
    df["quarter"] = ((df["reporting_month"] - 1) // 3 + 1).clip(1, 4)

    # ── Scope encoding ───────────────────────────────────────────────────
    # One-hot encoding: converts categorical scope values to 0/1 columns
    # XGBoost can handle numbers, not strings — encoding is mandatory
    scope_dummies = pd.get_dummies(df["scope"], prefix="scope")
    df = pd.concat([df, scope_dummies], axis=1)

    # ── Category encoding ─────────────────────────────────────────────────
    category_dummies = pd.get_dummies(df["category"], prefix="cat")
    df = pd.concat([df, category_dummies], axis=1)

    # ── Lag features (requires sorting) ─────────────────────────────────
    # Lag features: "what was the value 12 months ago?"
    # This is the single most powerful feature for time-series forecasting.
    # The model learns: "if emissions were high last January, they'll
    # probably be high this January too."
    df = df.sort_values(
        ["company_id", "scope", "category", "reporting_year", "reporting_month"]
    )
    group_cols = ["company_id", "scope", "category"]
    g = df.groupby(group_cols)["co2_tonnes"]

    # Lags only look at the past
    df["lag_1_month"] = g.shift(1)
    df["lag_12_months"] = g.shift(12)
    df["_lag_13"] = g.shift(13)  # helper column, not a model feature

    # Rolling stats run on the series shifted by one month,
    # so row t never sees its own value
    df["rolling_mean_3m"] = g.transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).mean()
    )
    df["rolling_std_12m"] = g.transform(
        lambda s: s.shift(1).rolling(12, min_periods=2).std()
    ).fillna(0)

    # Last month's year-over-year change: known at prediction time
    df["yoy_change"] = (
        (df["lag_1_month"] - df["_lag_13"]) / df["_lag_13"].replace(0, np.nan)
    ).fillna(0)

    return df


def get_feature_columns() -> list[str]:
    """
    Canonical list of features the model is trained on.
    Having this as a function prevents train/inference mismatch —
    the same function is called during training AND at inference time.
    This is a subtle but critical production practice.
    """
    return [
        "reporting_year",
        "reporting_month",
        "year_offset",
        "quarter",
        "month_sin",
        "month_cos",
        "lag_1_month",
        "lag_12_months",
        "rolling_mean_3m",
        "rolling_std_12m",
        "yoy_change",
        # Scope dummies — present/absent depending on training data
        "scope_scope_1",
        "scope_scope_2",
        "scope_scope_3",
        # Category dummies
        "cat_stationary_combustion",
        "cat_mobile_combustion",
        "cat_purchased_electricity",
        "cat_purchased_heat",
        "cat_business_travel",
        "cat_employee_commuting",
        "cat_supply_chain",
        "cat_waste",
        "cat_fuel_energy_related",
    ]


def prepare_features_and_target(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Final step before model training:
    - Select only the feature columns (drop IDs, raw strings)
    - Align columns (ensure all expected columns exist, fill missing with 0)
    - Drop rows with NaN in lag features (the first few rows per series)
    - Separate features (X) from target (y)
    """
    feature_cols = get_feature_columns()

    # Drop rows where lag features are NaN — can't train on incomplete rows
    df_clean = df.dropna(subset=["lag_1_month", "lag_12_months"])

    if df_clean.empty:
        raise ValueError(
            "No complete rows after dropping NaN lag features. "
            "Need at least 12 months of data per series."
        )

    # Align columns — add missing dummies as 0, drop unexpected columns
    X = df_clean.reindex(columns=feature_cols, fill_value=0)
    y = df_clean["co2_tonnes"]

    return X, y


def temporal_holdout_mask(X: pd.DataFrame, holdout_months: int = 6) -> pd.Series:
    """True for training rows, False for the most recent `holdout_months` months.

    Shared between train_with_mlflow and evaluate_forecasting so both always
    split on exactly the same calendar boundary — prevents the evaluation from
    accidentally scoring the model on rows it trained on.
    """
    period = X["reporting_year"] * 12 + X["reporting_month"]
    return period < (period.max() - holdout_months + 1)
