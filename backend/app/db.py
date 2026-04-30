import os
import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=1,
            max_size=10
        )

    return _pool


async def insert_url(
    filename,
    thumb,
    watermark,
    mime,
    size
) -> tuple[int, str]:
    """
    Insert row, then UPDATE the generated short_code.
    Returns (id, short_code).
    """
    from .shortener import encode

    pool = await get_pool()

    async with pool.acquire() as con:
        async with con.transaction():
            row = await con.fetchrow(
                """
                INSERT INTO urls
                (
                    short_code,
                    filename,
                    thumb_name,
                    watermark_name,
                    mime,
                    size_bytes
                )
                VALUES ('', $1, $2, $3, $4, $5)
                RETURNING id
                """,
                filename,
                thumb,
                watermark,
                mime,
                size
            )

            code = encode(row["id"])

            await con.execute(
                "UPDATE urls SET short_code = $1 WHERE id = $2",
                code,
                row["id"]
            )

            return row["id"], code


async def get_by_code(code: str):
    pool = await get_pool()

    async with pool.acquire() as con:
        return await con.fetchrow(
            "SELECT * FROM urls WHERE short_code = $1",
            code
        )