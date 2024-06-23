from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord
import git
import sentry_sdk
from dotenv import load_dotenv
from loguru import logger
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration

from hoyo_buddy.api import BotAPI
from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.logging import InterceptHandler
from hoyo_buddy.models import Config
from hoyo_buddy.web_server.server import GeetestWebServer

load_dotenv()
env = os.environ["ENV"]  # dev, prod, test
is_dev = env == "dev"

repo = git.Repo()
tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
version = tags[-1].name

parser = argparse.ArgumentParser()
parser.add_argument("--sentry", action="store_true", default=not is_dev)
parser.add_argument("--translator", action="store_true", default=not is_dev)
parser.add_argument("--search", action="store_true", default=not is_dev)
parser.add_argument("--schedule", action="store_true", default=not is_dev)

config = Config(parser.parse_args())

if config.sentry:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            LoguruIntegration(),
            AioHttpIntegration(transaction_style="method_and_path_pattern"),
            AsyncioIntegration(),
        ],
        traces_sample_rate=1.0,
        environment=env,
        enable_tracing=True,
        release=version,
    )

# Disables PyNaCl warning
discord.VoiceClient.warn_nacl = False


async def main() -> None:
    pool = await asyncpg.create_pool(os.environ["DB_URL"])
    if pool is None:
        msg = "Failed to connect to database"
        raise RuntimeError(msg)

    async with (
        aiohttp.ClientSession() as session,
        Database(),
        Translator(config) as translator,
        HoyoBuddy(
            session=session,
            env=env,
            translator=translator,
            repo=repo,
            version=version,
            pool=pool,
            config=config,
        ) as bot,
    ):
        with contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ):
            geetest_server = GeetestWebServer(translator=translator)
            api_server = BotAPI(bot)

            tasks: set[asyncio.Task] = set()
            task = asyncio.create_task(geetest_server.run())
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            task = asyncio.create_task(api_server.run())
            tasks.add(task)
            task.add_done_callback(tasks.discard)

            with bot.executor:
                await bot.start(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)
    logger.add("hoyo_buddy.log", rotation="32 MB", retention="5 days", level="INFO")

    try:
        from icecream import install
    except ImportError:
        pass
    else:
        install()

    try:
        import uvloop  # pyright: ignore [reportMissingImports]
    except ModuleNotFoundError:
        asyncio.run(main(), debug=True)
    else:
        uvloop.run(main(), debug=True)
