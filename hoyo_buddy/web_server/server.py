import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import web
from tortoise import Tortoise

from hoyo_buddy.db.models import User

from ..models import LoginNotifPayload
from .page import PAGE

if TYPE_CHECKING:
    from hoyo_buddy.bot.translator import Translator

LOGGER_ = logging.getLogger(__name__)
GT_V3_URL = "https://static.geetest.com/static/js/gt.0.5.0.js"
GT_V4_URL = "https://static.geetest.com/v4/gt4.js"


class GeetestWebServer:
    def __init__(self, translator: "Translator") -> None:
        self.translator = translator

    @staticmethod
    async def _get_mmt(user_id: int) -> dict[str, Any]:
        user = await User.get(id=user_id)
        return user.temp_data

    async def captcha(self, request: web.Request) -> web.StreamResponse:
        payload = LoginNotifPayload.parse_from_request(request)
        body = PAGE.format(
            user_id=payload.user_id,
            gt_version=payload.gt_version,
            api_server=payload.api_server,
            guild_id=payload.guild_id,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            proxy_geetest=payload.proxy_geetest,
        )
        return web.Response(body=body, content_type="text/html")

    async def gt(self, request: web.Request) -> web.StreamResponse:
        version = request.match_info.get("version", "v3")
        gt_url = GT_V4_URL if version == "v4" else GT_V3_URL

        async with aiohttp.ClientSession() as session, session.get(gt_url) as r:
            content = await r.read()

        return web.Response(body=content, content_type="text/javascript")

    async def mmt_endpoint(self, request: web.Request) -> web.Response:
        """Return the mmt of the user."""
        user_id = request.query["user_id"]
        mmt = await self._get_mmt(int(user_id))
        return web.json_response(mmt)

    async def send_data_endpoint(self, request: web.Request) -> web.Response:
        """Update user's temp_data with the solved geetest mmt and send a NOTIFY to the database."""
        data: dict[str, Any] = await request.json()

        user_id = data.pop("user_id")
        await User.filter(id=int(user_id)).update(temp_data=data)
        conn = Tortoise.get_connection("default")
        await conn.execute_query(f"NOTIFY geetest, '{user_id}'")

        return web.Response(status=204)

    async def redirect(self, request: web.Request) -> web.Response:
        """Redirect the user back to Discord with protocol link."""
        channel_id = request.query["channel_id"]
        guild_id = request.query["guild_id"]
        message_id = request.query["message_id"]

        protocol = (
            f"discord://-/channels/@me/{channel_id}/{message_id}"
            if guild_id == "null"
            else f"discord://-/channels/{guild_id}/{channel_id}/{message_id}"
        )
        return web.Response(status=302, headers={"Location": protocol})

    async def proxy(self, request: web.Request) -> web.Response:
        params = dict(request.query)
        url = params.pop("url", None)
        if not url:
            return web.Response(status=400)

        async with aiohttp.ClientSession() as session, session.get(url, params=params) as r:
            content = await r.read()

        return web.Response(body=content, status=r.status, content_type="text/javascript")

    async def run(self, port: int = 5000) -> None:
        LOGGER_.info("Starting web server... (port=%d)", port)

        app = web.Application()
        app.add_routes(
            [
                web.get("/captcha", self.captcha),
                web.get("/gt/{version}.js", self.gt),
                web.get("/mmt", self.mmt_endpoint),
                web.post("/send-data", self.send_data_endpoint),
                web.get("/redirect", self.redirect),
                web.get("/proxy", self.proxy),
            ]
        )

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", port)
        await site.start()
        LOGGER_.info("Web server started")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            LOGGER_.info("Web server shutting down...")
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()
