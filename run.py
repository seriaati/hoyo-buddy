from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import tracemalloc

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import POOL_MAX_WORKERS
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import entry_point, wrap_task_factory

tracemalloc.start()

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
discord.VoiceClient.warn_nacl = False


async def main() -> None:
    wrap_task_factory()

    if CONFIG.is_dev:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    else:
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=POOL_MAX_WORKERS)

    with (
        executor,
        contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ),
    ):
        async with (
            asyncpg.create_pool(CONFIG.db_url) as pool,
            aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session,
            Database(),
            translator,
            HoyoBuddy(session=session, pool=pool, config=CONFIG, executor=executor) as bot,
        ):
            await bot.start(CONFIG.discord_token)


if __name__ == "__main__":
    entry_point("logs/hoyo_buddy.log")
    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
