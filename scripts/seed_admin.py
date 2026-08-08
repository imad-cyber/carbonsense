"""
Run this once to create the first admin user:
    python scripts/seed_admin.py
"""
import sys
import os

# Add project root to path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserRole

db = SessionLocal()

try:
    admin = UserService.create(
        db,
        UserCreate(
            email="admin@carbonsense.fr",
            password="Admin1234",
            full_name="CarbonSense Admin",
            role=UserRole.ADMIN,
        ),
    )
    print(f"Admin created: {admin.email} (id={admin.id})")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()