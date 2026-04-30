import os
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import redis.asyncio as redis

router = APIRouter()
_r = None


def _client():
    global _r

    if _r is None:
        redis_url = os.environ.get("REDIS_URL")

        if not redis_url:
            raise HTTPException(503, "REDIS_URL is not configured")

        _r = redis.from_url(
            redis_url,
            decode_responses=True
        )

    return _r


async def broadcast_view(code: str) -> int:
    """
    Called by /s/{code}; returns the new count.
    """
    r = _client()

    count = await r.incr(f"views:{code}")

    await r.publish(
        f"chan:{code}",
        json.dumps({"views": count})
    )

    return count


@router.websocket("/ws/views/{code}")
async def ws_views(ws: WebSocket, code: str):
    r = _client()

    await ws.accept()

    # send current value immediately so the UI is not blank
    current = await r.get(f"views:{code}") or 0

    await ws.send_text(
        json.dumps({"views": int(current)})
    )

    pubsub = r.pubsub()
    await pubsub.subscribe(f"chan:{code}")

    try:
        async for msg in pubsub.listen():
            if msg["type"] != "message":
                continue

            await ws.send_text(msg["data"])

    except WebSocketDisconnect:
        pass

    finally:
        await pubsub.unsubscribe(f"chan:{code}")
        await pubsub.close()