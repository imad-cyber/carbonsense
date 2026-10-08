"""Which points drive the worst-series forecast error? Run: python scripts/worst_errors.py"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.ml.feature_engineering import (
    engineer_forecasting_features,
    load_emission_dataframe,
    prepare_features_and_target,
)

db = SessionLocal()
try:
    df_raw = load_emission_dataframe(db)
finally:
    db.close()

df = engineer_forecasting_features(df_raw)
X, y = prepare_features_and_target(df)
period = X["reporting_year"] * 12 + X["reporting_month"]
last12 = period > period.max() - 12   # the months covered by the 4 walk-forward folds
meta = df.loc[X.index, ["company_id", "scope", "category", "reporting_year", "reporting_month"]]
out = meta[last12].assign(
    actual=y[last12].round(1),
    same_month_last_year=X.loc[last12, "lag_12_months"].round(1),
)
out["error_pct"] = (
    (out["actual"] - out["same_month_last_year"]).abs() / out["actual"] * 100
).round(1)
print(out.sort_values("error_pct", ascending=False).head(12).to_string(index=False))
