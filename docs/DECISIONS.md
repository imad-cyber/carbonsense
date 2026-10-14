# Design decisions

Short records of the choices that shaped the project, with the evidence at the time.
Current numbers live in MODEL_CARD.md; they change when models are retrained.

## 1. Book only the combustion part of a factor as Scope 1 (generation as Scope 2)
**Context.** ADEME fuel and electricity factors are published as a total made of parts: combustion, upstream, and for electricity grid losses. The upstream part is not Scope 1 or 2.
**Decision.** Allocate each part to its scope: combustion to Scope 1, generation to Scope 2, upstream and grid losses to Scope 3 (fuel- and energy-related). Refuse part types that have not been reviewed.
**Evidence.** Booking the total as Scope 1 overstates it by about 19% for natural gas, 24% for road diesel, 3x for E85. In a public BEGES filing, the Scope 1 gas line and the Scope 2 electricity line match when only combustion and generation are booked (docs/VALIDATION_BEGES.md).
**Consequence.** Grid losses in Scope 3 follow secondary sources, not ADEME's own guidance. The whole policy is one table in `app/services/allocation.py`.

## 2. Snapshot the factor on every record; import factor releases as new versions
**Context.** Factors are revised yearly. A later update must not change an earlier figure.
**Decision.** Each record stores the factor id, version, the value and unit used and the part of the factor it came from. Imports add a version; they never overwrite.
**Consequence.** Figures stay reproducible. Records are wider.

## 3. The transparent baseline serves; XGBoost has to win every walk-forward fold
**Context.** The first XGBoost model scored R-squared 0.992 yet lost to "same month last year" (WAPE 6.65% against 5.49%). Pooled R-squared across series of very different size says little.
**Decision.** Serve "same month last year x trend factor". A challenger (XGBoost on the log-ratio to last year) takes over only if it wins every fold by at least 0.5 points of WAPE.
**Consequence.** On the synthetic data the served model is a one-line rule and the challenger ties it. The model card says so.

## 4. Anomalies: judge activity quantity, compare with the same month, flag a review queue
**Context.** Tonnes move when a factor is revised, which looked like an anomaly. Gas swings 45% with the seasons.
**Decision.** Score the activity quantity (tonnes divided by the factor). Compare with the same calendar month in other years, on log scales so spikes and drops count equally. Flag the most unusual 5% of a batch as a review queue. Identify a stream by an activity label, not by factor id.
**Evidence.** On the benchmark, obvious plants score about 0.99 against 0.85-0.91 for the earlier features, and obvious drops are found 99% of the time against 71-83%. A transparent same-month rule ties the model within noise (the model wins obvious plants, the rule wins subtle ones).
**Consequence.** Flags are not confirmed errors, and a clean company still gets flags. Only three planted anomalies exist in the demo, so the demo check is an illustration, not a benchmark.

## 5. API as a container on Railway, frontend on Vercel, experimental layers off
**Context.** The ML packages are large, and several early layers (RAG, WebSockets, Kafka, Airflow) were never run end to end.
**Decision.** Make heavy imports lazy, build `requirements-api.txt` from what the API really loads, ship the trained models in the image, and disable the experimental routes by default. The public demo uses a read-only account and a calculator that saves nothing; registration is off.
**Consequence.** Models are retrained locally and committed. No Redis in production, so caching degrades to off.
