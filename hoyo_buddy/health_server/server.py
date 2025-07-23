from __future__ import annotations

import asyncio

from aiohttp import web
from loguru import logger


class HealthWebServer:
    def __init__(self) -> None:
        self._login_template: str | None = None
        self._command_template: str | None = None

    async def health_check(self, _: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    async def run(self, *, port: int) -> None:
        logger.info(f"Starting health server on port {port}...")

        app = web.Application()
        app.add_routes([web.get("/health", self.health_check)])

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", port)
        await site.start()
        logger.info("Health server started")

        try:
            await asyncio.Future()
        except (KeyboardInterrupt, asyncio.CancelledError, SystemExit):
            logger.info("Health server shutting down...")
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()
