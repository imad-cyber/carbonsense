"""
Adds or removes one obviously fake factor to smoke-test the API before F2b.
  python scripts/test_factor.py add
  python scripts/test_factor.py remove
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.models.emission import EmissionRecord
from app.models.emission_factor import EmissionFactor

db = SessionLocal()
try:
    if sys.argv[1:] == ["add"]:
        f = EmissionFactor(
            source="TEST", source_id="fake-1", source_version="none",
            name="TEST ONLY - fake factor, not a real emission factor",
            unit="L", kg_co2e_per_unit=2.0, uncertainty_pct=10.0,
        )
        db.add(f)
        db.commit()
        print("added factor id", f.id)
    elif sys.argv[1:] == ["remove"]:
        ids = [f.id for f in db.query(EmissionFactor).filter(EmissionFactor.source == "TEST")]
        n_rec = db.query(EmissionRecord).filter(
            EmissionRecord.emission_factor_id.in_(ids)).delete(synchronize_session=False)
        n_fac = db.query(EmissionFactor).filter(EmissionFactor.source == "TEST").delete()
        db.commit()
        print(f"removed {n_rec} records and {n_fac} factors")
    else:
        print(__doc__)
finally:
    db.close()
