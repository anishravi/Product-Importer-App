from typing import Dict, List
from fastapi import WebSocket
import json


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a new WebSocket connection for a specific task."""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection."""
        if task_id in self.active_connections:
            if websocket in self.active_connections[task_id]:
                self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
    
    async def send_progress(self, websocket: WebSocket, message: dict):
        """Send progress update to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass  # Connection may have closed
    
    async def broadcast_progress(self, task_id: str, progress: float, processed: int, total: int, errors: List[dict]):
        """Broadcast progress update to all connections for a task."""
        message = {
            "type": "progress",
            "task_id": task_id,
            "progress": progress,
            "processed": processed,
            "total": total,
            "errors": errors
        }
        
        if task_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.disconnect(conn, task_id)
    
    async def broadcast_complete(self, task_id: str, success: bool, message: str):
        """Broadcast completion status to all connections for a task."""
        msg = {
            "type": "complete",
            "task_id": task_id,
            "success": success,
            "message": message
        }
        
        if task_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(msg)
                except Exception:
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for conn in disconnected:
                self.disconnect(conn, task_id)
    
    async def broadcast_webhook_test(self, webhook_id: int, result: dict):
        """Broadcast webhook test result."""
        message = {
            "type": "webhook_test",
            "webhook_id": webhook_id,
            "result": result
        }
        
        # Send to all connections (you might want to filter by webhook_id)
        for task_id, connections in list(self.active_connections.items()):
            disconnected = []
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            
            for conn in disconnected:
                self.disconnect(conn, task_id)


manager = ConnectionManager()

