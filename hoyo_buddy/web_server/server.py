from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any, Literal

import aiofiles
import aiohttp
from aiohttp import web
from loguru import logger
from tortoise import Tortoise

from hoyo_buddy.constants import WEB_APP_URLS
from hoyo_buddy.db.models import User
from hoyo_buddy.utils import get_discord_protocol_url

from ..enums import GeetestNotifyType
from ..models import GeetestPayload, LoginNotifPayload

if TYPE_CHECKING:
    from collections.abc import Callable

    from hoyo_buddy.l10n import Translator

GT_V3_URL = "https://static.geetest.com/static/js/gt.0.5.0.js"
GT_V4_URL = "https://static.geetest.com/v4/gt4.js"


class GeetestWebServer:
    def __init__(self, translator: Translator) -> None:
        self.translator = translator
        self._login_template: str | None = None
        self._command_template: str | None = None

    @web.middleware
    async def error_middleware(self, request: web.Request, handler: Callable) -> web.StreamResponse:
        try:
            return await handler(request)
        except web.HTTPException as e:
            return web.json_response({"error": e.reason}, status=e.status)
        except Exception:
            logger.exception("Error in web server")
            return web.json_response({"error": "Internal Server Error"}, status=500)

    @staticmethod
    async def _get_mmt(user_id: int) -> dict[str, Any]:
        user = await User.get(id=user_id)
        return user.temp_data

    async def captcha(self, request: web.Request) -> web.StreamResponse:
        try:
            if request.query["gt_type"] == "login":
                payload = GeetestPayload.parse_from_request(request.query)
                gt_type = GeetestNotifyType.LOGIN
            else:
                payload = LoginNotifPayload.parse_from_request(request.query)
                gt_type = GeetestNotifyType.COMMAND
        except ValueError as e:
            raise web.HTTPBadRequest(reason="Missing query parameter") from e

        if self._login_template is None or self._command_template is None:
            raise web.HTTPInternalServerError(reason="Template not loaded")

        if isinstance(payload, GeetestPayload):
            body = (
                self._login_template.replace("{ user_id }", str(payload.user_id))
                .replace("{ gt_version }", str(payload.gt_version))
                .replace("{ api_server }", payload.api_server)
                .replace("{ gt_type }", gt_type.value)  # noqa: RUF027
            )
        else:
            body = (
                self._command_template.replace("{ user_id }", str(payload.user_id))
                .replace("{ gt_version }", str(payload.gt_version))
                .replace("{ api_server }", payload.api_server)
                .replace("{ guild_id }", str(payload.guild_id))
                .replace("{ channel_id }", str(payload.channel_id))
                .replace("{ message_id }", str(payload.message_id))
                .replace("{ gt_type }", gt_type.value)  # noqa: RUF027
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

        geetest_type: Literal["login", "command"] = data.pop("gt_type")
        user_id = data.pop("user_id")
        await User.filter(id=user_id).update(temp_data=data)

        if geetest_type == "command":
            conn = Tortoise.get_connection("default")
            await conn.execute_query(f"NOTIFY geetest_{geetest_type}_{user_id}")

        return web.Response(status=204)

    async def redirect(self, request: web.Request) -> web.Response:
        """Redirect the user back to Discord with protocol link."""
        if "user_id" in request.query:
            # login
            user_id = request.query["user_id"]
            url = WEB_APP_URLS[os.environ["ENV"]] + f"/geetest?user_id={user_id}"
        else:
            # command
            channel_id = request.query["channel_id"]
            guild_id = request.query["guild_id"]
            message_id = request.query["message_id"]

            url = get_discord_protocol_url(
                channel_id=channel_id, guild_id=guild_id, message_id=message_id
            )
        return web.Response(status=302, headers={"Location": url})

    async def run(self, port: int = 5000) -> None:
        logger.info(f"Starting web server on port {port}...")

        async with aiofiles.open("hoyo_buddy/web_server/page_login.html") as f:
            self._login_template = await f.read()
        async with aiofiles.open("hoyo_buddy/web_server/page_command.html") as f:
            self._command_template = await f.read()

        app = web.Application(middlewares=[self.error_middleware])
        app.add_routes(
            [
                web.get("/captcha", self.captcha),
                web.get("/gt/{version}.js", self.gt),
                web.get("/mmt", self.mmt_endpoint),
                web.post("/send-data", self.send_data_endpoint),
                web.get("/redirect", self.redirect),
            ]
        )

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "localhost", port)
        await site.start()
        logger.info("Web server started")

        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Web server shutting down...")
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()
