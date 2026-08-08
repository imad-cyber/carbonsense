"""
Pytest fixtures shared across all tests.

- test_client:   FastAPI TestClient with a SQLite test database
- db_session:    SQLAlchemy session connected to the test DB (fresh per test)
- admin_token:   valid JWT for an admin user
- analyst_token: valid JWT for an analyst user
- sample_company: a Company row inserted into the test DB

The tests use a file-free SQLite database so they never require a running
PostgreSQL, Redis, Kafka, OpenAI or Airflow — external dependencies are
either disabled or gracefully degrade.
"""
import os
import tempfile

# Environment overrides MUST happen before importing app modules.
# The app's own engine is never used (get_db is overridden below), so the
# configured DATABASE_URL doesn't need to point at a live database.
_TMP = tempfile.mkdtemp(prefix="carbonsense_test_")
os.environ["MODEL_DIR"] = os.path.join(_TMP, "models")
os.environ["VECTOR_STORE_PATH"] = os.path.join(_TMP, "vector_store")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{os.path.join(_TMP, 'mlflow.db')}"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = ""  # disable Kafka in tests

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

# Force test-safe settings regardless of the developer's .env
settings.KAFKA_BOOTSTRAP_SERVERS = ""
settings.MODEL_DIR = os.environ["MODEL_DIR"]
settings.VECTOR_STORE_PATH = os.environ["VECTOR_STORE_PATH"]
os.makedirs(settings.MODEL_DIR, exist_ok=True)

from app.db.database import Base, get_db
from app.core.rate_limiter import limiter
from app.main import app
from app.core.security import create_access_token
from app.models.company import Company, IndustrySector
from app.models.user import User  # noqa: F401 — ensure table is registered
from app.models.emission import EmissionRecord  # noqa: F401
from app.core.cache import cache

# ── Test database (shared in-memory SQLite) ─────────────────────────────────
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # one shared connection → one shared in-memory DB
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Rate limiting needs Redis — disable globally, re-enable per-test when needed
limiter.enabled = False

REDIS_AVAILABLE = cache.ping()

requires_redis = pytest.mark.skipif(
    not REDIS_AVAILABLE, reason="Redis is not running locally"
)


@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_user(db, email: str, role: str) -> User:
    from app.core.security import hash_password

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password("Testpass1"),
            full_name=f"Test {role}",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture()
def admin_token(db_session) -> str:
    user = _make_user(db_session, "admin@example.com", "admin")
    return create_access_token(subject=user.email, role=user.role)


@pytest.fixture()
def analyst_token(db_session) -> str:
    user = _make_user(db_session, "analyst@example.com", "analyst")
    return create_access_token(subject=user.email, role=user.role)


@pytest.fixture()
def sample_company(db_session) -> Company:
    company = Company(
        name=f"Test Corp {os.urandom(4).hex()}",
        sector=IndustrySector.MANUFACTURING,
        country="France",
        employee_count=500,
        annual_revenue_eur=75_000,
    )
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)
    return company


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
