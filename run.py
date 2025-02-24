from __future__ import annotations

import asyncio
import contextlib

import aiohttp
import aiohttp.http_websocket
import asyncpg
import discord
from fake_useragent import UserAgent

from hoyo_buddy.bot import HoyoBuddy
from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import entry_point, wrap_task_factory
from hoyo_buddy.web_server.server import GeetestWebServer

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
    entry_point("logs/hoyo_buddy.log")
    try:
        import uvloop  # pyright: ignore[reportMissingImports]
    except ImportError:
        asyncio.run(main())
    else:
        uvloop.run(main())
