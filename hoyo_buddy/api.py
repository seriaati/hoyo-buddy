import asyncio
from typing import TYPE_CHECKING

import discord
from aiohttp import web
from loguru import logger

if TYPE_CHECKING:
    from .bot.bot import HoyoBuddy


class BotAPI:
    def __init__(self, bot: "HoyoBuddy") -> None:
        self._bot = bot

    async def index(self, _: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def commands(self, request: web.Request) -> web.Response:
        locale_value = request.query.get("locale")
        locale = (
            discord.Locale(locale_value)
            if locale_value is not None
            else discord.Locale.american_english
        )
        commands = self._bot.get_all_commands(locale)
        return web.json_response(commands)

    async def run(self, port: int = 7824) -> None:
        await self._bot.wait_until_ready()

        logger.info(f"Starting API server on port {port}...")

        app = web.Application()
        app.add_routes([web.get("/", self.index), web.get("/commands", self.commands)])

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", port)
        await site.start()
        logger.info("API server started")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("API server shutting down...")
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()
