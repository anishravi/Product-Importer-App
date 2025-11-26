import asyncio
import json
from typing import Any
import redis.asyncio as aioredis
from app.config import settings
from app.api.websocket import manager


async def redis_progress_subscriber() -> None:
    """Subscribe to Redis 'import_progress' channel and forward messages to WebSocket manager."""
    try:
        print("Starting Redis progress subscriber...")
        redis_client = aioredis.from_url(settings.redis_url)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe('import_progress')
        print("Subscribed to Redis 'import_progress' channel")

        # Listen for messages and forward
        async for message in pubsub.listen():
            # message example: {'type': 'message', 'channel': b'import_progress', 'data': b'...'}
            try:
                if message is None:
                    continue
                if message.get('type') != 'message':
                    continue
                data = message.get('data')
                if not data:
                    continue
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                
                print(f"Redis received: {data}")
                payload = json.loads(data)

                # Route by type
                msg_type = payload.get('type')
                task_id = payload.get('task_id')
                print(f"Processing message type: {msg_type} for task: {task_id}")
                
                if msg_type == 'progress':
                    progress = float(payload.get('progress', 0.0))
                    processed = int(payload.get('processed', 0))
                    total = int(payload.get('total', 0))
                    errors = payload.get('errors', []) or []
                    print(f"Broadcasting progress: {progress}% ({processed}/{total}) for task {task_id}")
                    # Broadcast to connected websocket clients
                    await manager.broadcast_progress(task_id, progress, processed, total, errors)
                elif msg_type == 'complete':
                    success = bool(payload.get('success', True))
                    message_text = payload.get('message', '')
                    print(f"Broadcasting completion: success={success}, message={message_text} for task {task_id}")
                    await manager.broadcast_complete(task_id, success, message_text)
                else:
                    print(f"Unknown message type: {msg_type}")
                    # Generic broadcast for other message types
                    if task_id:
                        await manager.broadcast_progress(task_id, float(payload.get('progress', 0.0)), int(payload.get('processed', 0)), int(payload.get('total', 0)), payload.get('errors', []))

            except Exception as e:
                # swallow errors to avoid subscriber exit
                print(f"Error processing Redis message: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Redis subscriber error: {e}")
        import traceback
        traceback.print_exc()
