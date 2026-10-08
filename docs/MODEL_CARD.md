# CarbonSense Model Card

Model trained: 20261007_024956

## Data
1697 monthly emission records. Sources: DEMO synthetic activity data, synthetic_training_data, unknown.

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
| obvious | 2% | abs(log(value / same-calendar-month median)) | 0.912 +/- 0.046 | 0.93 | 0.89 |
| obvious | 2% | abs(log(value / series median)) | 0.852 +/- 0.010 | 0.86 | 0.85 |
| obvious | 2% | abs(z-score) within series | 0.773 +/- 0.063 | 0.96 | 0.60 |
| obvious | 2% | Isolation Forest, raw tonnes included | 0.748 +/- 0.045 | 0.99 | 0.52 |
| obvious | 2% | Isolation Forest, log-ratio features | 0.906 +/- 0.039 | 0.90 | 0.90 |
| obvious | 2% | Isolation Forest, scale-free features (served) | 0.803 +/- 0.043 | 1.00 | 0.62 |
| obvious | 5% | abs(log(value / same-calendar-month median)) | 0.907 +/- 0.038 | 0.90 | 0.92 |
| obvious | 5% | abs(log(value / series median)) | 0.944 +/- 0.008 | 0.93 | 0.96 |
| obvious | 5% | abs(z-score) within series | 0.765 +/- 0.022 | 0.94 | 0.59 |
| obvious | 5% | Isolation Forest, raw tonnes included | 0.707 +/- 0.042 | 0.98 | 0.45 |
| obvious | 5% | Isolation Forest, log-ratio features | 0.942 +/- 0.016 | 0.93 | 0.95 |
| obvious | 5% | Isolation Forest, scale-free features (served) | 0.814 +/- 0.030 | 0.99 | 0.65 |
| subtle | 2% | abs(log(value / same-calendar-month median)) | 0.855 +/- 0.031 | 0.88 | 0.83 |
| subtle | 2% | abs(log(value / series median)) | 0.412 +/- 0.056 | 0.47 | 0.35 |
| subtle | 2% | abs(z-score) within series | 0.591 +/- 0.059 | 0.77 | 0.43 |
| subtle | 2% | Isolation Forest, raw tonnes included | 0.558 +/- 0.046 | 0.81 | 0.32 |
| subtle | 2% | Isolation Forest, log-ratio features | 0.770 +/- 0.026 | 0.83 | 0.71 |
| subtle | 2% | Isolation Forest, scale-free features (served) | 0.667 +/- 0.047 | 0.84 | 0.50 |
| subtle | 5% | abs(log(value / same-calendar-month median)) | 0.867 +/- 0.047 | 0.88 | 0.85 |
| subtle | 5% | abs(log(value / series median)) | 0.617 +/- 0.042 | 0.66 | 0.57 |
| subtle | 5% | abs(z-score) within series | 0.674 +/- 0.035 | 0.79 | 0.57 |
| subtle | 5% | Isolation Forest, raw tonnes included | 0.508 +/- 0.036 | 0.74 | 0.29 |
| subtle | 5% | Isolation Forest, log-ratio features | 0.820 +/- 0.036 | 0.87 | 0.78 |
| subtle | 5% | Isolation Forest, scale-free features (served) | 0.738 +/- 0.040 | 0.86 | 0.62 |

## Limitations
- All data is synthetic. Five companies come from `scripts/generate_training_data.py`: tonnes entered directly, smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. One demo company comes from `scripts/seed_demo_company.py`: synthetic activity quantities converted with real ADEME Base Carbone V23.6 factors. Recovering the built-in trend factor only confirms what the generators put in.
- Three anomalies in the demo company were planted by the author, so finding them illustrates the detector and does not benchmark it.
- Anomalies are planted by multiplication, which favours log-ratio scorers. Distance-from-median scoring ranked them almost perfectly on the five smooth synthetic companies, but fell to about 85% once a strongly seasonal series (gas, plus or minus 45%) was added: a planted spike in a seasonal trough hides under normal winter peaks. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- The forecast evaluation window contains the demo company's planted anomalies (June 2024 electricity, and February 2024 gas through its "same month last year" value). They produce the largest errors and drive the worst-series MAPE; the median series MAPE (about 6%) is not affected.
- Each run plants only about 28 to 72 anomalies; differences smaller than the reported spread are not meaningful.
- Production flags use an assumed 5% contamination rate, so about 5% of records are flagged whatever the data quality. The benchmark ranks records and does not use that threshold.
- Severity labels (high, medium, low) come from a simple rule on the deviation from the series median, not from a calibrated model.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data.