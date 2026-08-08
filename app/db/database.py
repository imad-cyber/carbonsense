from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# The engine is the core interface to the database
# pool_pre_ping = true means that sqlalchemy tests the connection before using it
# this prevents "connection lost" errors in long running apps
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10, # max 10 persistent connections in the pool
    max_overflow=20 # up to 20 extra connections if pool is full
)

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