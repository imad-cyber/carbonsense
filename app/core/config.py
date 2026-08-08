from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "CarbonSense"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CACHE_TTL_SUMMARY: int = 900
    CACHE_TTL_COMPANY_LIST: int = 300

    # ML settings
    # MLflow stores experiment logs, metrics, and model artifacts here
    MLFLOW_TRACKING_URI: str = "sqlite:///mlflow.db"
    # Why SQLite for MLflow locally? Zero-config. In production
    # you'd point this at a PostgreSQL MLflow server.
    MLFLOW_EXPERIMENT_NAME: str = "carbonsense-emissions"

    # Where trained model files are saved on disk
    MODEL_DIR: str = "models"

    # Minimum model performance to accept a new model
    # If R² drops below this, we reject the new model and keep the old one
    # This is called a "model quality gate" — it's in every MLOps pipeline
    MIN_FORECAST_R2: float = 0.70
    ANOMALY_CONTAMINATION: float = 0.05  # expected % of anomalies in data

    # RAG / LLM settings (Phase 7)
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"
    VECTOR_STORE_PATH: str = "vector_store"
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200

    # Kafka settings (Phase 8) — empty string disables Kafka entirely
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_EMISSION_TOPIC: str = "emission-events"
    KAFKA_ALERT_TOPIC: str = "emission-alerts"

    # Comma-separated list of allowed frontend origins
    CORS_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()

# Create model directory on startup if it doesn't exist
Path(settings.MODEL_DIR).mkdir(exist_ok=True)