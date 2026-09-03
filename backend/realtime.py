"""
Real-time Connection Manager for Candway ATS
P1-001 FIX: Improved WebSocket handling with heartbeats, limits, and proper cleanup.

Handles:
- WebSocket connections for live notifications, presence, and chat
- Connection heartbeats/ping-pong for detecting dead connections
- Maximum connections per user limit
- Proper async cleanup to prevent memory leaks
"""

import asyncio
import logging
import time
from typing import Dict

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Configuration
MAX_CONNECTIONS_PER_USER = 5  # Limit concurrent connections per user
CONNECTION_TIMEOUT_SECONDS = 300  # 5 minutes - disconnect if no activity
HEARTBEAT_INTERVAL_SECONDS = 30  # Send ping every 30 seconds


class ConnectionManager:
    """
    Manages active WebSocket connections by user ID with:
    - Heartbeat mechanism for connection health
    - Maximum connections per user
    - Connection timeout handling
    - Proper async cleanup
    """

    def __init__(self):
        # user_id -> set of active WebSockets with metadata
        self.active_connections: Dict[int, Dict[WebSocket, dict]] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> bool:
        """
        Register a new connection for a user.

        Returns:
            True if connection accepted, False if limit exceeded
        """
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = {}

            # Check connection limit
            current_count = len(self.active_connections[user_id])
            if current_count >= MAX_CONNECTIONS_PER_USER:
                logger.warning(
                    f"User {user_id} rejected: too many connections ({current_count})"
                )
                await websocket.close(code=1008, reason="Too many connections")
                return False

            # Accept the connection
            await websocket.accept()

            # Store with metadata
            self.active_connections[user_id][websocket] = {
                "connected_at": time.time(),
                "last_ping": time.time(),
                "client_info": str(websocket.client),
            }

            logger.info(f"User {user_id} connected. Total: {current_count + 1}")
            return True

    async def disconnect(self, websocket: WebSocket, user_id: int):
        async with self._lock:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    del self.active_connections[user_id][websocket]

                    remaining = len(self.active_connections.get(user_id, {}))
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]

                    logger.info(f"User {user_id} disconnected. Remaining: {remaining}")

    async def update_ping(self, websocket: WebSocket, user_id: int):
        """Update last ping timestamp for connection"""
        async with self._lock:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id][websocket]["last_ping"] = (
                        time.time()
                    )

    async def send_personal_message(self, message: dict, user_id: int) -> int:
        """
        Send a message to all active connections of a specific user.

        Returns:
            Number of connections message was sent to
        """
        async with self._lock:
            if user_id not in self.active_connections:
                return 0

            websockets = list(self.active_connections[user_id].keys())
            sent_count = 0

            for websocket in websockets:
                try:
                    await websocket.send_json(message)
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send to user {user_id}: {e}")
                    # Remove dead connection
                    del self.active_connections[user_id][websocket]

            return sent_count

    async def broadcast(self, message: dict):
        """Send a message to all connected users"""
        async with self._lock:
            dead_connections = []
            for user_id, connections in self.active_connections.items():
                for websocket in list(connections.keys()):
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Failed to broadcast: {e}")
                        dead_connections.append((user_id, websocket))

            # Remove dead connections
            for user_id, ws in dead_connections:
                if user_id in self.active_connections:
                    self.active_connections[user_id].pop(ws, None)
                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]

    async def get_online_users(self) -> list[int]:
        async with self._lock:
            return list(self.active_connections.keys())

    async def get_connection_count(self, user_id: int) -> int:
        async with self._lock:
            return len(self.active_connections.get(user_id, {}))

    async def cleanup_stale_connections(self):
        """
        Periodic task to remove stale connections.
        Connections without ping for CONNECTION_TIMEOUT_SECONDS are disconnected.
        """
        async with self._lock:
            current_time = time.time()
            stale_threshold = current_time - CONNECTION_TIMEOUT_SECONDS

            stale_users = []
            for user_id, connections in self.active_connections.items():
                stale_websockets = [
                    ws
                    for ws, meta in connections.items()
                    if meta.get("last_ping", 0) < stale_threshold
                ]

                for ws in stale_websockets:
                    try:
                        await ws.close(code=1000, reason="Connection timeout")
                    except Exception:
                        pass  # Already closed
                    del connections[ws]
                    logger.info(f"Cleaned up stale connection for user {user_id}")

                if not connections:
                    stale_users.append(user_id)

            # Remove empty user entries
            for user_id in stale_users:
                del self.active_connections[user_id]


# Global manager instance
manager = ConnectionManager()


async def start_heartbeat_scheduler():
    """
    Start background task to clean up stale connections.
    Should be called on application startup.
    """
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await manager.cleanup_stale_connections()
        except asyncio.CancelledError:
            logger.info("Heartbeat scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in heartbeat scheduler: {e}")


# Helper functions for WebSocket endpoints
async def handle_websocket_ping(websocket: WebSocket, user_id: int):
    try:
        await websocket.receive_text()
        await manager.update_ping(websocket, user_id)
    except Exception:
        pass


async def send_heartbeat(websocket: WebSocket):
    try:
        await websocket.send_json({"type": "ping", "timestamp": time.time()})
    except Exception:
        pass
