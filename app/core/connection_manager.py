"""
ConnectionManager — registry of active WebSocket connections.

Supports broadcasting to all clients, to a single client, or to every
client watching a specific company (client_id prefix "company:{id}:").
"""
import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.
    A lock guards the registry — connections come and go from
    multiple concurrent async tasks.
    """

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept the WebSocket and register it."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connected: {client_id} ({len(self.active_connections)} active)")
        try:
            from app.core.metrics import active_websocket_connections
            active_websocket_connections.inc()
        except Exception:  # noqa: BLE001 — metrics must never break connections
            pass

    def disconnect(self, client_id: str) -> None:
        """Remove a connection from the registry."""
        removed = self.active_connections.pop(client_id, None)
        if removed is not None:
            logger.info(f"WebSocket disconnected: {client_id}")
            try:
                from app.core.metrics import active_websocket_connections
                active_websocket_connections.dec()
            except Exception:  # noqa: BLE001
                pass

    async def send_to_client(self, client_id: str, data: dict) -> None:
        """Send a JSON message to a specific client. Ignores missing/dead clients."""
        websocket = self.active_connections.get(client_id)
        if websocket is None:
            return
        try:
            await websocket.send_json(data)
        except Exception:  # noqa: BLE001 — client hung up mid-send
            self.disconnect(client_id)

    async def broadcast(self, data: dict) -> None:
        """Send a JSON message to ALL connected clients."""
        for client_id in list(self.active_connections.keys()):
            await self.send_to_client(client_id, data)

    async def broadcast_to_company(self, company_id: int, data: dict) -> None:
        """Send only to clients watching a specific company's data."""
        prefix = f"company:{company_id}:"
        for client_id in list(self.active_connections.keys()):
            if client_id.startswith(prefix):
                await self.send_to_client(client_id, data)

    def get_connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()  # module singleton
