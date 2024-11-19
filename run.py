from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import sys

import aiohttp
import aiohttp.http_websocket
import asyncpg
from fake_useragent import UserAgent
import discord
from dotenv import load_dotenv
from loguru import logger

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import Translator
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.models import Config
from hoyo_buddy.utils import init_sentry, wrap_task_factory
from hoyo_buddy.web_server.server import GeetestWebServer

load_dotenv()
env = os.environ["ENV"]  # dev, prod, test
is_dev = env == "dev"
ua = UserAgent()

parser = argparse.ArgumentParser()
parser.add_argument("--sentry", action="store_true", default=not is_dev)
parser.add_argument("--search", action="store_true", default=not is_dev)
parser.add_argument("--schedule", action="store_true", default=not is_dev)

config = Config(parser.parse_args())
discord.VoiceClient.warn_nacl = False


async def main() -> None:
    wrap_task_factory()

    async with (
        asyncpg.create_pool(os.environ["DB_URL"]) as pool,
        aiohttp.ClientSession(headers={"User-Agent": ua.random}) as session,
        Database(),
        Translator() as translator,
        HoyoBuddy(session=session, env=env, translator=translator, pool=pool, config=config) as bot,
    ):
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError):
            geetest_server = GeetestWebServer(translator=translator)

            asyncio.create_task(geetest_server.run())

            with bot.executor:
                await bot.start(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    logger.remove()

    if config.sentry:
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

    try:
        import uvloop  # pyright: ignore [reportMissingImports]
    except ModuleNotFoundError:
        asyncio.run(main())
    else:
        uvloop.run(main())
