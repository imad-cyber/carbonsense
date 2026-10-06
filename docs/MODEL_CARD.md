# CarbonSense Model Card

Model trained: 20261007_021504

## Data
1697 monthly emission records. Sources: DEMO synthetic activity data, synthetic_training_data, unknown.

**All results below are on synthetic data.** They show the pipeline works end to end, not that the models predict real company emissions.

## Forecasting

Served model: **Same month last year x trend factor**. Trend factor: 0.9677.

Walk-forward evaluation: 4 folds, each trained on the past and scored on the next 3 months of every series. The challenger replaces the baseline only if it wins every fold and improves mean WAPE by at least 0.5 percentage points. Differences smaller than that are within fold-to-fold noise.

Mean over folds:

| Method | MAE (t CO2e) | WAPE % | Median series MAPE % | Worst series MAPE % |
|---|---|---|---|---|
| Same month last year | 293.12 | 6.79 | 6.2 | 44.09 |
| Same month last year x trend factor | 275.88 | 6.32 | 6.17 | 41.37 |
| XGBoost on log-ratio to last year | 274.18 | 6.26 | 6.33 | 39.86 |

WAPE per fold (1 = most recent):

| Fold | Baseline | Challenger |
|---|---|---|
| 1 | 7.03 | 7.07 |
| 2 | 4.59 | 5.54 |
| 3 | 6.05 | 5.5 |
| 4 | 7.62 | 6.92 |

## Anomaly detection

Anomalies were planted by multiplying random records up (spikes) or down (drops). Each scorer ranks every record by suspiciousness; precision@k is the share of the top k that are planted anomalies, with k = number planted. Mean +/- std over 10 seeds. The served detector is the scale-free Isolation Forest.

| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found |
|---|---|---|---|---|---|
| obvious | 2% | |log(value / series median)| | 0.852 +/- 0.010 | 0.86 | 0.85 |
| obvious | 2% | |z-score| within series | 0.779 +/- 0.066 | 0.96 | 0.61 |
| obvious | 2% | Isolation Forest, raw tonnes included | 0.742 +/- 0.026 | 0.99 | 0.51 |
| obvious | 2% | Isolation Forest, scale-free features | 0.794 +/- 0.045 | 1.00 | 0.60 |
| obvious | 5% | |log(value / series median)| | 0.944 +/- 0.008 | 0.93 | 0.96 |
| obvious | 5% | |z-score| within series | 0.771 +/- 0.018 | 0.95 | 0.60 |
| obvious | 5% | Isolation Forest, raw tonnes included | 0.710 +/- 0.046 | 0.98 | 0.45 |
| obvious | 5% | Isolation Forest, scale-free features | 0.815 +/- 0.032 | 0.99 | 0.65 |
| subtle | 2% | |log(value / series median)| | 0.412 +/- 0.056 | 0.47 | 0.35 |
| subtle | 2% | |z-score| within series | 0.585 +/- 0.066 | 0.77 | 0.41 |
| subtle | 2% | Isolation Forest, raw tonnes included | 0.558 +/- 0.050 | 0.81 | 0.32 |
| subtle | 2% | Isolation Forest, scale-free features | 0.670 +/- 0.039 | 0.85 | 0.49 |
| subtle | 5% | |log(value / series median)| | 0.618 +/- 0.038 | 0.67 | 0.57 |
| subtle | 5% | |z-score| within series | 0.685 +/- 0.038 | 0.81 | 0.57 |
| subtle | 5% | Isolation Forest, raw tonnes included | 0.506 +/- 0.041 | 0.73 | 0.29 |
| subtle | 5% | Isolation Forest, scale-free features | 0.730 +/- 0.036 | 0.86 | 0.60 |

## Limitations
- All data is synthetic. Five companies come from `scripts/generate_training_data.py`: tonnes entered directly, smooth seasonality, a built-in 3% annual decline and about 5% Gaussian noise. One demo company comes from `scripts/seed_demo_company.py`: synthetic activity quantities converted with real ADEME Base Carbone V23.6 factors. Recovering the built-in trend factor only confirms what the generators put in.
- Three anomalies in the demo company were planted by the author, so finding them illustrates the detector and does not benchmark it.
- Anomalies are planted by multiplication, so ranking by distance from the series median scores near-perfectly by construction. That says nothing about real reporting errors such as unit mistakes, double counting or missing months.
- The detector compares each record with the series median, not with the same calendar month, so seasonal peaks look mildly unusual.
- Each run plants only about 28 to 72 anomalies; differences smaller than the reported spread are not meaningful.
- Production flags use an assumed 5% contamination rate, so about 5% of records are flagged whatever the data quality. The benchmark ranks records and does not use that threshold.
- Severity labels (high, medium, low) come from a simple rule on the deviation from the series median, not from a calibrated model.
- Forecasts are supported only for the month right after the latest data.
- There has been no validation on real company data.