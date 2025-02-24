from __future__ import annotations

import asyncio
import contextlib
import logging
import sys

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord
from fake_useragent import UserAgent
from loguru import logger

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.config import CONFIG, parse_args
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.utils import init_sentry, wrap_task_factory
from hoyo_buddy.web_server.server import GeetestWebServer

is_dev = CONFIG.env == "dev"
ua = UserAgent()

discord.VoiceClient.warn_nacl = False


async def main() -> None:
    wrap_task_factory()

    async with (
        asyncpg.create_pool(CONFIG.db_url) as pool,
        aiohttp.ClientSession(headers={"User-Agent": ua.random}) as session,
        Database(),
        translator,
        HoyoBuddy(session=session, pool=pool, config=CONFIG) as bot,
    ):
        with contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ):
            geetest_server = GeetestWebServer()

            asyncio.create_task(geetest_server.run())

            with bot.executor:
                await bot.start(CONFIG.discord_token)


if __name__ == "__main__":
    logger.remove()

    args = parse_args(default=CONFIG.env == "prod")
    CONFIG.update_from_args(args)

    if CONFIG.sentry:
        init_sentry()

    logger.add(sys.stderr, level="DEBUG" if is_dev else "INFO")
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add("logs/hoyo_buddy.log", rotation="1 day", retention="2 weeks", level="DEBUG")

    try:
        from icecream import install
    except ImportError:
        pass
    else:
        install()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
