# CarbonSense Model Card

Model trained: 20261002_071238

## Data
1440 monthly emission records. Sources: synthetic_training_data.

**All results below are on synthetic data.** They show the pipeline works end to end, not that the models predict real company emissions.

## Forecasting

Served model: **Same month last year x trend factor**. Trend factor: 0.9670.

Walk-forward evaluation: 4 folds, each trained on the past and scored on the next 3 months of every series. The challenger replaces the baseline only if it wins every fold and improves mean WAPE by at least 0.5 percentage points. Differences smaller than that are within fold-to-fold noise.

Mean over folds:

| Method | MAE (t CO2e) | WAPE % | Median series MAPE % | Worst series MAPE % |
|---|---|---|---|---|
| Same month last year | 321.65 | 6.78 | 6.25 | 12.91 |
| Same month last year x trend factor | 303.23 | 6.32 | 6.42 | 12.56 |
| XGBoost on log-ratio to last year | 303.12 | 6.29 | 6.27 | 12.74 |

WAPE per fold (1 = most recent):

| Fold | Baseline | Challenger |
|---|---|---|
| 1 | 7.06 | 7.19 |
| 2 | 4.62 | 5.72 |
| 3 | 6.01 | 5.46 |
| 4 | 7.6 | 6.81 |

## Anomaly detection

Anomalies were planted by multiplying random records up (spikes) or down (drops). Each scorer ranks every record by suspiciousness; precision@k is the share of the top k that are planted anomalies, with k = number planted. Mean +/- std over 10 seeds. The served detector is the scale-free Isolation Forest.

| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found |
|---|---|---|---|---|---|
| obvious | 2% | |log(value / series median)| | 1.000 +/- 0.000 | 1.00 | 1.00 |
| obvious | 2% | |z-score| within series | 0.871 +/- 0.054 | 0.99 | 0.76 |
| obvious | 2% | Isolation Forest, raw tonnes included | 0.857 +/- 0.053 | 1.00 | 0.74 |
| obvious | 2% | Isolation Forest, scale-free features | 0.907 +/- 0.025 | 1.00 | 0.83 |
| obvious | 5% | |log(value / series median)| | 1.000 +/- 0.000 | 1.00 | 1.00 |
| obvious | 5% | |z-score| within series | 0.803 +/- 0.053 | 0.99 | 0.63 |
| obvious | 5% | Isolation Forest, raw tonnes included | 0.761 +/- 0.051 | 0.99 | 0.55 |
| obvious | 5% | Isolation Forest, scale-free features | 0.851 +/- 0.011 | 1.00 | 0.72 |
| subtle | 2% | |log(value / series median)| | 0.696 +/- 0.051 | 0.77 | 0.65 |
| subtle | 2% | |z-score| within series | 0.654 +/- 0.053 | 0.82 | 0.53 |
| subtle | 2% | Isolation Forest, raw tonnes included | 0.668 +/- 0.065 | 0.85 | 0.53 |
| subtle | 2% | Isolation Forest, scale-free features | 0.782 +/- 0.049 | 0.89 | 0.70 |
| subtle | 5% | |log(value / series median)| | 0.769 +/- 0.028 | 0.81 | 0.73 |
| subtle | 5% | |z-score| within series | 0.731 +/- 0.050 | 0.85 | 0.63 |
| subtle | 5% | Isolation Forest, raw tonnes included | 0.660 +/- 0.040 | 0.85 | 0.49 |
| subtle | 5% | Isolation Forest, scale-free features | 0.800 +/- 0.028 | 0.90 | 0.71 |

## Limitations
- All data is synthetic, from `scripts/generate_training_data.py`: smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. A forecaster cannot be shown to beat a baseline on data this regular, and recovering the trend factor only confirms the built-in decline.
- Anomalies are planted by multiplication, so ranking by distance from the series median scores near-perfectly by construction. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- The detector compares each record with the series median, not with the same calendar month, so seasonal peaks look mildly unusual.
- Each run plants only about 28 to 72 anomalies; differences smaller than the reported spread are not meaningful.
- Production flags use an assumed 5% contamination rate, so about 5% of records are flagged whatever the data quality. The benchmark ranks records and does not use that threshold.
- Severity labels (high, medium, low) come from a simple rule on the deviation from the series median, not from a calibrated model.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data.