"""
WebSocket endpoints for real-time features:
- /ws/live/{company_id}   → live emission feed + on-demand anomaly scoring
- /ws/tasks/{client_id}   → push notifications when Celery tasks complete

JWT is passed as a query parameter (?token=...) because browsers cannot
set custom headers on WebSocket connections.
"""
import logging
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError

from app.core.connection_manager import manager
from app.core.dependencies import require_admin
from app.core.security import decode_access_token
from app.db.database import SessionLocal
from app.models.user import User
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _authenticate_ws_token(token: str) -> User | None:
    """
    Validate the JWT from the query param and load the user.
    Uses its own short-lived DB session — WebSocket handshakes happen
    outside the normal request dependency lifecycle.
    """
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None

    db = SessionLocal()
    try:
        user = UserService.get_by_email(db, email)
        if user is None or not user.is_active:
            return None
        return user
    finally:
        db.close()


@router.websocket("/live/{company_id}")
async def live_emissions_feed(
    websocket: WebSocket,
    company_id: int,
    token: str = "",
):
    """
    Live emission updates for a company.

    Message schema (both directions):
        {"type": str, "payload": dict, "timestamp": ISO8601}

    Client → server message types:
    - "score_record":    payload is an emission record dict → returns anomaly score
    - "ping":            returns {"type": "pong"}
    - "subscribe_tasks": registers this client for task completion broadcasts
    """
    user = _authenticate_ws_token(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    client_id = f"company:{company_id}:{user.id}"
    await manager.connect(websocket, client_id)

    await manager.send_to_client(client_id, {
        "type": "connected",
        "payload": {"company_id": company_id, "user": user.email},
        "timestamp": _now(),
    })

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type", "")
            payload = message.get("payload", {})

            if msg_type == "ping":
                await manager.send_to_client(client_id, {
                    "type": "pong", "payload": {}, "timestamp": _now(),
                })

            elif msg_type == "score_record":
                await manager.send_to_client(client_id, {
                    "type": "score_result",
                    "payload": _score_single_record(company_id, payload),
                    "timestamp": _now(),
                })

            elif msg_type == "subscribe_tasks":
                # Task completion notifications are broadcast to all clients;
                # acknowledging keeps the client protocol explicit.
                await manager.send_to_client(client_id, {
                    "type": "subscribed",
                    "payload": {"channel": "tasks"},
                    "timestamp": _now(),
                })

            else:
                await manager.send_to_client(client_id, {
                    "type": "error",
                    "payload": {"detail": f"Unknown message type '{msg_type}'"},
                    "timestamp": _now(),
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:  # noqa: BLE001 — never leave dead entries in the registry
        logger.warning(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


def _score_single_record(company_id: int, payload: dict) -> dict:
    """Score one emission record with the anomaly detector (graceful if untrained)."""
    from app.ml.model_registry import load_model, model_exists

    if not model_exists("anomaly_detector"):
        return {"error": "Anomaly detector not trained yet"}

    try:
        from app.ml.anomaly_detector import build_anomaly_features
        from app.ml.feature_engineering import load_emission_dataframe
        import pandas as pd

        bundle = load_model("anomaly_detector")["model"]
        model, scaler = bundle["model"], bundle["scaler"]

        db = SessionLocal()
        try:
            df = load_emission_dataframe(db, company_id=company_id)
        finally:
            db.close()

        candidate = pd.DataFrame([{
            "id": -1,
            "company_id": company_id,
            "scope": payload.get("scope", "scope_1"),
            "category": payload.get("category", "stationary_combustion"),
            "co2_tonnes": float(payload.get("co2_tonnes", 0)),
            "reporting_year": int(payload.get("reporting_year", datetime.now().year)),
            "reporting_month": int(payload.get("reporting_month", 1)),
            "data_source": "live_scoring",
        }])
        df_all = pd.concat([df, candidate], ignore_index=True) if not df.empty else candidate

        df_features = build_anomaly_features(df_all)
        row = df_features[df_features["id"] == -1]
        feature_cols = ["co2_tonnes", "z_score", "ratio_to_median",
                        "mom_change", "reporting_month"]
        X = scaler.transform(row[feature_cols].fillna(0))

        is_anomaly = bool(model.predict(X)[0] == -1)
        score = float(model.decision_function(X)[0])
        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": round(score, 4),
            "co2_tonnes": float(payload.get("co2_tonnes", 0)),
        }
    except Exception as e:  # noqa: BLE001 — return the error to the client instead
        logger.warning(f"Live scoring failed: {e}")
        return {"error": f"Scoring failed: {e}"}


@router.websocket("/tasks/{client_id}")
async def task_notifications(websocket: WebSocket, client_id: str, token: str = ""):
    """
    Push notifications when Celery tasks complete — the frontend connects
    once instead of polling /api/v1/tasks/{id}.
    """
    user = _authenticate_ws_token(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    registry_id = f"tasks:{client_id}:{user.id}"
    await manager.connect(websocket, registry_id)

    await manager.send_to_client(registry_id, {
        "type": "connected",
        "payload": {"channel": "tasks", "user": user.email},
        "timestamp": _now(),
    })

    try:
        while True:
            # Keep the connection open; respond to pings, ignore the rest
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await manager.send_to_client(registry_id, {
                    "type": "pong", "payload": {}, "timestamp": _now(),
                })
    except WebSocketDisconnect:
        manager.disconnect(registry_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Task notification WS error for {registry_id}: {e}")
        manager.disconnect(registry_id)


@router.post("/broadcast/{company_id}")
async def broadcast_to_company(
    company_id: int,
    payload: dict,
    _: User = Depends(require_admin),
):
    """Admin endpoint to manually broadcast a message to a company's watchers."""
    await manager.broadcast_to_company(company_id, {
        "type": "broadcast",
        "payload": payload,
        "timestamp": _now(),
    })
    return {"sent_to": manager.get_connection_count(), "company_id": company_id}
