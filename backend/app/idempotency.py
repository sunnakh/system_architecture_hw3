import os
import json
import functools
import asyncio

from fastapi import HTTPException, Request
import redis.asyncio as redis

_r: redis.Redis | None = None

TTL = 24 * 3600        # 24 hours
PENDING_TTL = 60       # seconds a single request may take


def _client():
    global _r

    if _r is None:
        _r = redis.from_url(
            os.environ["REDIS_URL"],
            decode_responses=True
        )

    return _r


def idempotent(fn):
    """
    Cache the JSON response under X-Request-ID.
    Handles concurrent retries with a PENDING sentinel.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        req: Request = kwargs["request"]

        rid = req.headers.get("X-Request-ID")

        if not rid:
            raise HTTPException(
                400,
                "X-Request-ID header is required"
            )

        key = f"idem:{rid}"
        r = _client()

        # Phase 1: reserve the key, or see a cached hit
        ok = await r.set(
            key,
            "PENDING",
            nx=True,
            ex=PENDING_TTL
        )

        if not ok:
            # someone else owns this key
            for _ in range(30):   # ~3 seconds
                val = await r.get(key)

                if val and val != "PENDING":
                    return json.loads(val)

                await asyncio.sleep(0.1)

            raise HTTPException(
                409,
                "Request still in progress"
            )

        # Phase 2: do the real work
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            await r.delete(key)   # let client retry
            raise

        # Phase 3: cache and return
        await r.set(
            key,
            json.dumps(result),
            ex=TTL
        )

        return result

    return wrapper