import logging
import joblib
from pathlib import Path
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_DIR = Path(settings.MODEL_DIR)


def save_model(model, name: str, metadata: dict = None) -> Path:
    """
    Saves a trained model to disk with a versioned filename.

    Versioning strategy: timestamp + model name.
    In production you'd use semantic versioning (v1.2.3) tied to
    the MLflow run ID. For now, timestamp is sufficient.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = MODEL_DIR / f"{name}_{timestamp}.joblib"

    payload = {
        "model": model,
        "metadata": metadata or {},
        "saved_at": timestamp,
        "name": name,
    }
    joblib.dump(payload, filename)
    logger.info(f"Model saved: {filename}")

    # Also save as 'latest' — this is what inference loads
    # This two-file pattern means: old version stays on disk for rollback,
    # 'latest' pointer always points at the newest accepted model
    latest_path = MODEL_DIR / f"{name}_latest.joblib"
    joblib.dump(payload, latest_path)
    logger.info(f"Latest pointer updated: {latest_path}")

    return filename


def load_model(name: str):
    """
    Loads the latest version of a named model.
    Returns None if no model exists yet — inference endpoints
    handle this gracefully rather than crashing.
    """
    latest_path = MODEL_DIR / f"{name}_latest.joblib"

    if not latest_path.exists():
        logger.warning(f"No model found at {latest_path}")
        return None

    payload = joblib.load(latest_path)
    logger.info(
        f"Model loaded: {name} "
        f"(saved at {payload.get('saved_at', 'unknown')})"
    )
    return payload


def model_exists(name: str) -> bool:
    return (MODEL_DIR / f"{name}_latest.joblib").exists()