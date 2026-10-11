"""
On the demo company, where do the planted anomalies rank under each scorer?
An illustration with 3 planted anomalies, not a benchmark.   python scripts/demo_anomaly_ranks.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

from app.db.database import SessionLocal
from app.ml.anomaly_detector import build_anomaly_features
from app.ml.evaluation import LOG_FEATURES, SCALE_FREE_FEATURES, _iso_rank
from app.ml.feature_engineering import load_emission_dataframe
from app.models.company import Company

COMPANY = "Démo Industrie SA (synthetic activity data)"

db = SessionLocal()
try:
    company_id = db.query(Company.id).filter(Company.name == COMPANY).scalar()
    df = load_emission_dataframe(db)
finally:
    db.close()

feats = build_anomaly_features(df).sort_index()   # all companies, as in training
scorers = {
    "iso_scale_free (served)": _iso_rank(feats, SCALE_FREE_FEATURES),
    "iso_log_features": _iso_rank(feats, LOG_FEATURES),
    "abs_log_ratio_same_month": feats["log_ratio_same_month"].abs().to_numpy(),
}
mine = (feats["company_id"] == company_id).to_numpy()
known = feats["known_anomaly"].to_numpy(dtype=bool)
idx = np.flatnonzero(mine)

for name, s in scorers.items():
    order = idx[np.argsort(-s[idx])]
    rank = {i: r + 1 for r, i in enumerate(order)}
    planted = sorted(rank[i] for i in idx if known[i])
    print(f"{name}: planted records ranked {planted} of {len(idx)}; "
          f"{max(planted) - len(planted)} unplanted records rank above the last planted one")
