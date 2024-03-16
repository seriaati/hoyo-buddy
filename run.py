import asyncio
import contextlib
import logging
import os

import aiohttp
import discord
import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration
from seria.logging import setup_logging

from hoyo_buddy.bot.bot import HoyoBuddy
from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.web_server.server import GeetestWebServer

load_dotenv()
env = os.environ["ENV"]

if env == "prod":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)],
        traces_sample_rate=1.0,
    )

# Disables PyNaCl warning
discord.VoiceClient.warn_nacl = False


async def main() -> None:
    async with (
        aiohttp.ClientSession() as session,
        Database(),
        Translator(env) as translator,
        HoyoBuddy(session=session, env=env, translator=translator) as bot,
    ):
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
            server = GeetestWebServer(translator=translator)
            asyncio.create_task(server.run())
            await bot.start(os.environ["DISCORD_TOKEN"])


with setup_logging(
    logging.DEBUG if env == "dev" else logging.INFO,
    loggers_to_suppress=(
        "aiosqlite",
        "tortoise.db_client",
        "PIL",
        "aiohttp_client_cache",
        "transifex",
    ),
    log_filename="hoyo_buddy.log",
):
    try:
        import uvloop  # type: ignore
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
