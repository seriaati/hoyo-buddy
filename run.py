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

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import POOL_MAX_WORKERS
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils.start import (
    setup_async_event_loop,
    setup_logging,
    setup_sentry,
    wrap_task_factory,
)

tracemalloc.start()

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
CACHE_EXPIRE = 12 * 3600  # 12 hours
discord.VoiceClient.warn_nacl = False


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
            url=CONFIG.redis_url, namespace="hoyo_buddy_cache", expire_after=3600
        )
    else:
        backend = SQLiteBackend(cache_name="hoyo_buddy_cache", expire_after=3600, fast_save=True)

    with (
        executor,
        contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ),
    ):
        async with (
            asyncpg.create_pool(CONFIG.db_url) as pool,
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
        ):
            await bot.start(CONFIG.discord_token)


if __name__ == "__main__":
    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
