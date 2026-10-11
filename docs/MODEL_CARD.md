# CarbonSense Model Card

Model trained: 20261012_023820

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

Anomalies were planted by multiplying random records up (spikes) or down (drops); the demo company's known planted records count as positives too. Each scorer ranks every record by suspiciousness; precision@k is the share of the top k that are positives, with k = number of positives. Mean +/- std over 10 seeds.

| Planted | Rate | Scorer | Precision@k | Spikes found | Drops found | Demo planted found |
|---|---|---|---|---|---|---|
| obvious | 2% | abs(log(value / same-calendar-month median)) | 0.975 +/- 0.031 | 0.97 | 0.98 | 0.99 |
| obvious | 2% | abs(log(value / series median)) | 1.000 +/- 0.000 | 1.00 | 1.00 | 1.00 |
| obvious | 2% | abs(z-score) within series | 0.840 +/- 0.039 | 0.99 | 0.69 | 0.87 |
| obvious | 2% | Isolation Forest, raw tonnes included | 0.840 +/- 0.052 | 0.99 | 0.70 | 0.84 |
| obvious | 2% | Isolation Forest, log-ratio features (served) | 0.997 +/- 0.008 | 1.00 | 0.99 | 1.00 |
| obvious | 2% | Isolation Forest, scale-free features (previous) | 0.910 +/- 0.027 | 1.00 | 0.83 | 0.90 |
| obvious | 5% | abs(log(value / same-calendar-month median)) | 0.954 +/- 0.022 | 0.95 | 0.96 | 0.94 |
| obvious | 5% | abs(log(value / series median)) | 0.993 +/- 0.006 | 0.99 | 1.00 | 1.00 |
| obvious | 5% | abs(z-score) within series | 0.795 +/- 0.043 | 0.97 | 0.62 | 0.80 |
| obvious | 5% | Isolation Forest, raw tonnes included | 0.720 +/- 0.041 | 0.99 | 0.48 | 0.60 |
| obvious | 5% | Isolation Forest, log-ratio features (served) | 0.989 +/- 0.007 | 0.99 | 0.99 | 1.00 |
| obvious | 5% | Isolation Forest, scale-free features (previous) | 0.845 +/- 0.031 | 1.00 | 0.71 | 0.77 |
| subtle | 2% | abs(log(value / same-calendar-month median)) | 0.945 +/- 0.039 | 0.94 | 0.92 | 1.00 |
| subtle | 2% | abs(log(value / series median)) | 0.573 +/- 0.058 | 0.58 | 0.40 | 1.00 |
| subtle | 2% | abs(z-score) within series | 0.710 +/- 0.066 | 0.85 | 0.47 | 1.00 |
| subtle | 2% | Isolation Forest, raw tonnes included | 0.595 +/- 0.070 | 0.81 | 0.24 | 1.00 |
| subtle | 2% | Isolation Forest, log-ratio features (served) | 0.910 +/- 0.024 | 0.94 | 0.84 | 1.00 |
| subtle | 2% | Isolation Forest, scale-free features (previous) | 0.802 +/- 0.045 | 0.93 | 0.60 | 1.00 |
| subtle | 5% | abs(log(value / same-calendar-month median)) | 0.924 +/- 0.023 | 0.94 | 0.89 | 1.00 |
| subtle | 5% | abs(log(value / series median)) | 0.690 +/- 0.024 | 0.72 | 0.62 | 1.00 |
| subtle | 5% | abs(z-score) within series | 0.724 +/- 0.029 | 0.80 | 0.61 | 1.00 |
| subtle | 5% | Isolation Forest, raw tonnes included | 0.565 +/- 0.035 | 0.78 | 0.29 | 1.00 |
| subtle | 5% | Isolation Forest, log-ratio features (served) | 0.889 +/- 0.020 | 0.92 | 0.84 | 1.00 |
| subtle | 5% | Isolation Forest, scale-free features (previous) | 0.798 +/- 0.028 | 0.90 | 0.67 | 1.00 |

## Demo company check

The served detector, run over the demo company's 108 activity entries (2022-2024), produced 6 findings. It found 3 of the 3 planted anomalies; the other 3 findings are not planted (false alarms or genuine extremes; the data has no other labelled errors). Three planted anomalies make this an illustration, not a benchmark.

## Limitations
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
- There has been no validation on real company data. The Scope 1 and 2 accounting lines of one published filing were reproduced (docs/VALIDATION_BEGES.md); that validates the arithmetic and allocation policy for those lines, not the models.