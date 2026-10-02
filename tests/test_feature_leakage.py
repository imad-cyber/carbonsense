import pandas as pd
from app.ml.feature_engineering import (
    engineer_forecasting_features,
    get_feature_columns,
)


def _series(n: int = 30) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "company_id": 1, "scope": "scope_1", "category": "stationary_combustion",
            "co2_tonnes": 100.0 + i,
            "reporting_year": 2022 + i // 12, "reporting_month": i % 12 + 1,
        }
        for i in range(n)
    ])


def test_features_do_not_depend_on_the_current_target():
    """
    Changing the final row's co2_tonnes must not affect any feature column
    for that same row. If it does, the model can 'see' what it is predicting,
    which is pure data leakage.
    """
    cols = get_feature_columns()
    df = _series()
    a = engineer_forecasting_features(df).reindex(columns=cols, fill_value=0)

    df_changed = df.copy()
    df_changed.loc[df_changed.index[-1], "co2_tonnes"] = 99_999.0  # change only the target

    b = engineer_forecasting_features(df_changed).reindex(columns=cols, fill_value=0)

    pd.testing.assert_series_equal(
        a.iloc[-1].astype(float),
        b.iloc[-1].astype(float),
        check_names=False,
    )
