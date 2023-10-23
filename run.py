import asyncio
import contextlib
import logging
import logging.handlers
import os

import aiohttp
import discord
import sentry_sdk
from discord.ext import commands
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.db import Database

try:
    import uvloop  # type: ignore
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

load_dotenv()
prod = os.getenv("PROD", "0") == "1"

if prod:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
        traces_sample_rate=1.0,
    )

# Disables PyNaCl warning
discord.VoiceClient.warn_nacl = False


class RemoveNoise(logging.Filter):
    def __init__(self):
        super().__init__(name="discord.state")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelname == "WARNING" and "referencing an unknown" in record.msg:
            return False
        return True


async def main():
    intents = discord.Intents(
        guilds=True,
        members=True,
        emojis=True,
        guild_messages=True,
    )
    allowed_mentions = discord.AllowedMentions(
        users=True,
        everyone=False,
        roles=False,
        replied_user=False,
    )
    session = aiohttp.ClientSession()
    bot = HoyoBuddy(
        command_prefix=commands.when_mentioned,
        intents=intents,
        case_insensitive=True,
        session=session,
        allowed_mentions=allowed_mentions,
        help_command=None,
        chunk_guilds_at_startup=False,
        max_messages=None,
    )
    db = Database(os.getenv("DB_URL") or "sqlite://db.sqlite3")

    async with session, db, bot:
        try:
            await bot.start(os.environ["DISCORD_TOKEN"])
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass


@contextlib.contextmanager
def setup_logging():
    log = logging.getLogger()

    try:
        discord.utils.setup_logging()
        # __enter__
        max_bytes = 32 * 1024 * 1024  # 32 MiB
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("discord.state").addFilter(RemoveNoise())

        log.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            filename="hoyo_buddy.log",
            encoding="utf-8",
            mode="w",
            maxBytes=max_bytes,
            backupCount=5,
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        fmt = logging.Formatter(
            "[{asctime}] [{levelname:<7}] {name}: {message}", dt_fmt, style="{"
        )
        handler.setFormatter(fmt)
        log.addHandler(handler)

        yield
    finally:
        # __exit__
        handlers = log.handlers[:]
        for handler in handlers:
            handler.close()
            log.removeHandler(handler)


with setup_logging():
    asyncio.run(main())
