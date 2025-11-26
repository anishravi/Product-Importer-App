from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.websocket import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time progress updates."""
    await manager.connect(websocket, task_id)
    try:
        # Send initial connection message
        await websocket.send_json({"type": "connected", "task_id": task_id})
        
        while True:
            try:
                # Keep connection alive and handle any client messages
                data = await websocket.receive_text()
                # Echo back or handle client messages if needed
                await websocket.send_json({"type": "pong", "message": "connected"})
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket, task_id)

