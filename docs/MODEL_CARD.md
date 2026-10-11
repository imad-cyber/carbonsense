# CarbonSense Model Card

Model trained: 20261007_024956

## Data
1692 monthly emission records. Sources: DEMO synthetic activity data, synthetic_training_data.

**All results below are on synthetic data.** They show the pipeline works end to end, not that the models predict real company emissions.

## Forecasting

Served model: **Same month last year x trend factor**. Trend factor: 0.9677.

Walk-forward evaluation: 4 folds, each trained on the past and scored on the next 3 months of every series. The challenger replaces the baseline only if it wins every fold and improves mean WAPE by at least 0.5 percentage points. Differences smaller than that are within fold-to-fold noise.

Mean over folds:

| Method | MAE (t CO2e) | WAPE % | Median series MAPE % | Worst series MAPE % |
|---|---|---|---|---|
| Same month last year | 293.32 | 6.79 | 6.35 | 51.15 |
| Same month last year x trend factor | 275.95 | 6.33 | 6.34 | 46.45 |
| XGBoost on log-ratio to last year | 277.55 | 6.34 | 6.31 | 43.02 |

WAPE per fold (1 = most recent):

| Fold | Baseline | Challenger |
|---|---|---|
| 1 | 7.02 | 7.12 |
| 2 | 4.57 | 5.59 |
| 3 | 6.09 | 5.67 |
| 4 | 7.62 | 6.98 |

## Anomaly detection

Anomalies were planted by multiplying random records up (spikes) or down (drops). Each scorer ranks every record by suspiciousness; precision@k is the share of the top k that are planted anomalies, with k = number planted. Mean +/- std over 10 seeds. The served detector is the scale-free Isolation Forest.

| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found |
|---|---|---|---|---|---|
| obvious | 2% | abs(log(value / same-calendar-month median)) | 0.835 +/- 0.054 | 0.91 | 0.89 |
| obvious | 2% | abs(log(value / series median)) | 1.000 +/- 0.000 | 1.00 | 1.00 |
| obvious | 2% | abs(z-score) within series | 0.835 +/- 0.053 | 0.99 | 0.67 |
| obvious | 2% | Isolation Forest, raw tonnes included | 0.845 +/- 0.052 | 0.99 | 0.69 |
| obvious | 2% | Isolation Forest, log-ratio features | 0.975 +/- 0.012 | 0.98 | 0.97 |
| obvious | 2% | Isolation Forest, scale-free features (served) | 0.912 +/- 0.032 | 1.00 | 0.81 |
| obvious | 5% | abs(log(value / same-calendar-month median)) | 0.860 +/- 0.019 | 0.88 | 0.89 |
| obvious | 5% | abs(log(value / series median)) | 0.993 +/- 0.006 | 0.99 | 1.00 |
| obvious | 5% | abs(z-score) within series | 0.788 +/- 0.042 | 0.96 | 0.61 |
| obvious | 5% | Isolation Forest, raw tonnes included | 0.725 +/- 0.037 | 0.99 | 0.48 |
| obvious | 5% | Isolation Forest, log-ratio features | 0.982 +/- 0.014 | 0.98 | 0.98 |
| obvious | 5% | Isolation Forest, scale-free features (served) | 0.848 +/- 0.029 | 1.00 | 0.71 |
| subtle | 2% | abs(log(value / same-calendar-month median)) | 0.810 +/- 0.050 | 0.89 | 0.83 |
| subtle | 2% | abs(log(value / series median)) | 0.573 +/- 0.058 | 0.58 | 0.40 |
| subtle | 2% | abs(z-score) within series | 0.715 +/- 0.068 | 0.85 | 0.49 |
| subtle | 2% | Isolation Forest, raw tonnes included | 0.600 +/- 0.047 | 0.81 | 0.25 |
| subtle | 2% | Isolation Forest, log-ratio features | 0.887 +/- 0.038 | 0.93 | 0.81 |
| subtle | 2% | Isolation Forest, scale-free features (served) | 0.818 +/- 0.044 | 0.93 | 0.64 |
| subtle | 5% | abs(log(value / same-calendar-month median)) | 0.837 +/- 0.024 | 0.87 | 0.85 |
| subtle | 5% | abs(log(value / series median)) | 0.688 +/- 0.026 | 0.71 | 0.61 |
| subtle | 5% | abs(z-score) within series | 0.721 +/- 0.033 | 0.79 | 0.61 |
| subtle | 5% | Isolation Forest, raw tonnes included | 0.565 +/- 0.028 | 0.77 | 0.30 |
| subtle | 5% | Isolation Forest, log-ratio features | 0.878 +/- 0.015 | 0.91 | 0.83 |
| subtle | 5% | Isolation Forest, scale-free features (served) | 0.808 +/- 0.027 | 0.90 | 0.69 |

## Limitations
- All data is synthetic. Five companies come from `scripts/generate_training_data.py`: tonnes entered directly, smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. One demo company comes from `scripts/seed_demo_company.py`: synthetic activity quantities converted with real ADEME Base Carbone V23.6 factors. Recovering the built-in trend factor only confirms what the generators put in.
- Three anomalies in the demo company were planted by the author (seven records, because each activity creates several). The benchmark counts them as known positives. Finding them illustrates the detector and does not benchmark it.
- Benchmark anomalies are planted by multiplication, which favours log-ratio scorers. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- When last run on the demo company, the served detector flagged 17 of 108 activities over 2022-2024: the 3 planted ones and 14 normal seasonal extremes (13 in gas, which swings about 45% between winter and summer, and 1 in electricity in July). The detector compares each record with the series median, not with the same calendar month.
- The "high" severity label is a fixed rule on the ratio to the series median (at least 2x or at most 0.5x). The planted anomalies were chosen beyond those thresholds, so "all high-severity findings are planted" is true by construction and is not a measure of detection quality.
- Each benchmark run plants only about 2% or 5% of records; differences smaller than the reported spread are not meaningful.
- Production flags use a contamination rate fixed at training time (5% of training records), whatever the data quality. The benchmark ranks records and does not use that threshold.
- The forecast evaluation window contains the demo company's planted anomalies (June 2024 electricity, and February 2024 gas through its "same month last year" value). They produce the largest errors and drive the worst-series MAPE; the median series MAPE (about 6%) is not affected.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data. The Scope 1 and 2 accounting lines of one published filing were reproduced (docs/VALIDATION_BEGES.md); that validates the arithmetic and allocation policy for those lines, not the models.