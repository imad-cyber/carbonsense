import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.models.emission import EmissionRecord


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
    df = df.sort_values(["company_id", "scope", "category",
                         "reporting_year", "reporting_month"])

    # Group by company+scope+category to compute lags within each series
    group_cols = ["company_id", "scope", "category"]
    df["lag_1_month"] = df.groupby(group_cols)["co2_tonnes"].shift(1)
    df["lag_12_months"] = df.groupby(group_cols)["co2_tonnes"].shift(12)

    # ── Rolling statistics ────────────────────────────────────────────────
    # 3-month rolling mean: smooths noise, captures trend direction
    df["rolling_mean_3m"] = (
        df.groupby(group_cols)["co2_tonnes"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )
    # 12-month rolling std: captures emission volatility
    df["rolling_std_12m"] = (
        df.groupby(group_cols)["co2_tonnes"]
        .transform(lambda x: x.rolling(12, min_periods=1).std().fillna(0))
    )

    # ── YoY change ────────────────────────────────────────────────────────
    # Year-over-year percent change — encodes the reduction trend
    df["yoy_change"] = (
        (df["co2_tonnes"] - df["lag_12_months"]) /
        df["lag_12_months"].replace(0, np.nan)
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