"""
Prints a short-lived JWT for an existing user, for local testing. Creates no accounts.
Never deploy this script.   python scripts/dev_token.py admin@carbonsense.fr
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import create_access_token
from app.db.database import SessionLocal
from app.models.user import User

email = sys.argv[1] if len(sys.argv) == 2 else sys.exit(__doc__)
db = SessionLocal()
try:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        sys.exit(f"No active user {email}. Create it with scripts/seed_admin.py.")
    print(create_access_token(subject=user.email, role=user.role))
finally:
    db.close()
