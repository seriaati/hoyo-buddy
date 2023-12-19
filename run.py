import asyncio
import contextlib
import logging
import os

import aiohttp
import discord
import sentry_sdk
from discord.ext import commands
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.bot.command_tree import CommandTree
from hoyo_buddy.bot.logging import setup_logging
from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db import Database
from hoyo_buddy.db.redis import RedisPool

try:
    import uvloop  # type: ignore
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

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

    async with aiohttp.ClientSession() as session, Database(), RedisPool(
        os.environ["REDIS_URI"]
    ) as redis_pool, Translator(env) as translator, HoyoBuddy(
        session=session,
        env=env,
        redis_pool=redis_pool,
        translator=translator,
        command_prefix=commands.when_mentioned,
        intents=intents,
        case_insensitive=True,
        allowed_mentions=allowed_mentions,
        help_command=None,
        chunk_guilds_at_startup=False,
        max_messages=None,
        tree_cls=CommandTree,
    ) as bot:
        with contextlib.suppress(KeyboardInterrupt, asyncio.CancelledError):
            await bot.start(os.environ["DISCORD_TOKEN"])


with setup_logging(env):
    asyncio.run(main())
