from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import tracemalloc

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord
from aiohttp_client_cache.backends.redis import RedisBackend
from aiohttp_client_cache.backends.sqlite import SQLiteBackend
from aiohttp_client_cache.session import CachedSession
from loguru import logger

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import POOL_MAX_WORKERS
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.health import HealthCheckServer
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import setup_async_event_loop, setup_logging, setup_sentry, wrap_task_factory

tracemalloc.start()

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
CACHE_EXPIRE = 12 * 3600  # 12 hours
discord.VoiceClient.warn_nacl = False


async def create_db_pool_with_retry(
    db_url: str, max_retries: int = 5, initial_delay: float = 1.0
) -> asyncpg.Pool:
    """Create database pool with exponential backoff retry logic."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to database (attempt {attempt + 1}/{max_retries})")
            pool = await asyncpg.create_pool(db_url)
        except (OSError, asyncpg.PostgresError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to database after {max_retries} attempts")
                raise
            delay = initial_delay * (2**attempt)
            logger.warning(f"Database connection failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
        else:
            logger.info("Successfully connected to database")
            return pool
    msg = "Unreachable code"
    raise RuntimeError(msg)


async def main() -> None:
    wrap_task_factory()
    setup_logging("logs/hoyo_buddy.log")
    setup_async_event_loop()
    setup_sentry(CONFIG.bot_sentry_dsn)

    if CONFIG.is_dev:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=POOL_MAX_WORKERS)
    else:
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=POOL_MAX_WORKERS)

    if CONFIG.redis_url is not None:
        backend = RedisBackend(
            address=CONFIG.redis_url, cache_name="hoyo_buddy", expire_after=CACHE_EXPIRE
        )
    else:
        backend = SQLiteBackend(cache_name=".cache/hoyo_buddy", expire_after=CACHE_EXPIRE)

    with (
        executor,
        contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ),
    ):
        pool = await create_db_pool_with_retry(CONFIG.db_url)
        async with (
            pool,
            aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
            CachedSession(cache=backend) as cache_session,
            Database(),
            translator,
            HoyoBuddy(
                session=session,
                cache_session=cache_session,
                pool=pool,
                config=CONFIG,
                executor=executor,
            ) as bot,
            HealthCheckServer(bot, port=8081),
        ):
            await bot.start(CONFIG.discord_token)


if __name__ == "__main__":
    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
