from collections.abc import AsyncIterator

import asyncpg

from denmark_academy.config import get_settings


async def create_pool() -> asyncpg.Pool:
    settings = get_settings()
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=10,
        timeout=settings.database_connect_timeout_seconds,
        command_timeout=30,
    )


async def ping_database() -> bool:
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return True
    finally:
        await pool.close()


async def connection() -> AsyncIterator[asyncpg.Connection]:
    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            yield conn
    finally:
        await pool.close()

