import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

_is_serverless = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))

# Serverless invocations must not hold a connection pool between requests.
_engine_kwargs: dict = {"pool_pre_ping": True}
if _is_serverless:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)

# SessionLocal is the factory that creates new database sessions
# Each request gets its own session - this is crucial for data safety.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the class all our models will inherit from
# its what ties python classes to database tables
Base = declarative_base()

# dependency injection
# for one request a db session is created
# it closes it when that request is done
# the yield keyword makes it a context manager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()