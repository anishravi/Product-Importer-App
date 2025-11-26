from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.websocket import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time progress updates."""
    await manager.connect(websocket, task_id)
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected", 
            "task_id": task_id,
            "message": f"Connected to task {task_id}"
        })
        print(f"WebSocket connected for task {task_id}")
        
        while True:
            try:
                # Keep connection alive and handle any client messages
                data = await websocket.receive_text()
                print(f"WebSocket received: {data} for task {task_id}")
                # Echo back or handle client messages if needed
                await websocket.send_json({
                    "type": "pong", 
                    "message": "connection alive",
                    "task_id": task_id
                })
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket receive error for task {task_id}: {e}")
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        print(f"WebSocket error for task {task_id}: {e}")
    finally:
        manager.disconnect(websocket, task_id)
        print(f"WebSocket cleanup completed for task {task_id}")

