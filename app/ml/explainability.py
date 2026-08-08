import logging
import numpy as np
import pandas as pd
import shap
from xgboost import XGBRegressor
from app.ml.feature_engineering import get_feature_columns

logger = logging.getLogger(__name__)


def explain_prediction(
    model: XGBRegressor,
    X_row: pd.DataFrame,
) -> dict:
    """
    Generates a SHAP explanation for a single prediction.

    SHAP (SHapley Additive exPlanations) answers:
    "This model predicted 45,000t CO₂. Why?"

    For each feature it calculates a SHAP value:
    - Positive value: this feature INCREASED the prediction
    - Negative value: this feature DECREASED the prediction
    - Magnitude: how much impact this feature had

    Example output:
    base_value: 38,000  (average prediction across all training data)
    lag_12_months: +5,200  (same month last year was high, pushing up)
    month_sin: +1,800  (January = heating season, pushing up)
    rolling_mean_3m: -800  (recent trend was declining, pushing down)
    → final prediction: 38,000 + 5,200 + 1,800 - 800 = 44,200

    This is EXACTLY what CSRD auditors need: not just a number,
    but a traceable explanation of what drove it.
    """
    # TreeExplainer is optimised for tree-based models (XGBoost, LightGBM)
    # It's exact (not approximate) and very fast for tree models
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_row)

    feature_names = get_feature_columns()

    # Build a ranked list of feature contributions
    contributions = []
    for feat_name, shap_val in zip(feature_names, shap_values[0], strict=False):
        if abs(shap_val) > 0.01:  # ignore negligible contributions
            contributions.append({
                "feature": feat_name,
                "feature_value": float(X_row.iloc[0][feat_name])
                if feat_name in X_row.columns else 0.0,
                "shap_value": float(shap_val),
                "direction": "increases_emission"
                if shap_val > 0 else "decreases_emission",
            })

    # Sort by absolute SHAP value — most impactful features first
    contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)

    return {
        "base_value": float(explainer.expected_value),
        "prediction": float(model.predict(X_row)[0]),
        "top_drivers": contributions[:10],  # top 10 most impactful features
        "explanation_method": "SHAP TreeExplainer",
    }


def get_global_feature_importance(
    model: XGBRegressor,
    X: pd.DataFrame,
    n_top: int = 15,
) -> list[dict]:
    """
    Global feature importance across ALL predictions.
    This is the 'big picture' — which features matter most overall?

    Uses mean(|SHAP|) — the average absolute SHAP value per feature.
    This is better than XGBoost's built-in importance which can
    be misleading for features with many unique values.
    """
    explainer = shap.TreeExplainer(model)

    # Sample for speed if dataset is large
    X_sample = X.sample(min(500, len(X)), random_state=42)
    shap_values = explainer.shap_values(X_sample)

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    feature_names = get_feature_columns()

    importance = [
        {
            "feature": name,
            "importance": float(val),
            "rank": rank + 1,
        }
        for rank, (name, val)
        in enumerate(
            sorted(
                zip(feature_names, mean_abs_shap, strict=False),
                key=lambda x: x[1],
                reverse=True,
            )
        )
    ]

    return importance[:n_top]