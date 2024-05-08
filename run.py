import asyncio
import contextlib
import logging
import os
from concurrent.futures import ProcessPoolExecutor

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord
import git
import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from seria.logging import setup_logging

from hoyo_buddy.bot.bot import HoyoBuddy
from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.web_server.server import GeetestWebServer

load_dotenv()
env = os.environ["ENV"]  # dev, prod, test

repo = git.Repo()
tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
version = tags[-1].name

if env != "dev":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.WARNING),
            AioHttpIntegration(transaction_style="method_and_path_pattern"),
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

    with (
        ProcessPoolExecutor() as executor,
        contextlib.suppress(
            KeyboardInterrupt, asyncio.CancelledError, aiohttp.http_websocket.WebSocketError
        ),
    ):
        async with (
            aiohttp.ClientSession() as session,
            Database(),
            Translator(env) as translator,
            HoyoBuddy(
                session=session,
                env=env,
                translator=translator,
                repo=repo,
                version=version,
                pool=pool,
                executor=executor,
            ) as bot,
        ):
            server = GeetestWebServer(translator=translator)
            tasks: set[asyncio.Task] = set()
            task = asyncio.create_task(server.run())
            tasks.add(task)
            task.add_done_callback(tasks.discard)

            await bot.start(os.environ["DISCORD_TOKEN"])


with setup_logging(logging.INFO, log_filename="hoyo_buddy.log"):
    try:
        import uvloop  # pyright: ignore [reportMissingImports]
    except ModuleNotFoundError:
        asyncio.run(main(), debug=True)
    else:
        uvloop.run(main(), debug=True)
