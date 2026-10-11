"""
Creates (or resets) the read-only demo login, role 'auditor': it can read data and use
the calculator preview, but cannot write.   python scripts/seed_demo_user.py
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.user import User

EMAIL = "demo@carbonsense.fr"
PASSWORD = "Demo-Auditor-2026"   # public on purpose; the account is read-only

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == EMAIL).first()
    if user is None:
        user = User(email=EMAIL, hashed_password=hash_password(PASSWORD),
                    full_name="Demo (read-only)", role="auditor", is_active=True)
        db.add(user)
    else:
        user.hashed_password = hash_password(PASSWORD)
        user.role, user.is_active = "auditor", True
    db.commit()
    print(f"demo login ready: {EMAIL} (role auditor)")
finally:
    db.close()
