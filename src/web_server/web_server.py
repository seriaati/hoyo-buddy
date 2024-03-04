import asyncio
import logging
from typing import Any, Literal

import aiofiles
import aiohttp
from aiohttp import web
from discord import Locale
from tortoise import Tortoise

from src.bot.translator import LocaleStr, Translator
from src.db.models import User

from ..hoyo.dataclasses import LoginNotifPayload

LOGGER_ = logging.getLogger(__name__)
GT_URL = "https://raw.githubusercontent.com/GeeTeam/gt3-node-sdk/master/demo/static/libs/gt.js"


class GeetestWebServer:
    def __init__(self, translator: Translator) -> None:
        self.translator = translator

    @staticmethod
    async def _get_mmt(user_id: int) -> dict[str, Any]:
        user = await User.get(id=user_id)
        return user.temp_data

    async def _get_page(
        self, page: Literal["captcha", "verify-email"], payload: LoginNotifPayload
    ) -> str:
        locale = Locale(payload.locale)

        async with aiofiles.open(f"src/web_server/pages/{page}.html", encoding="utf-8") as f:
            content = await f.read()

        content = (
            content.replace(
                "<!-- SEND -->",
                self.translator.translate(
                    LocaleStr(
                        "Send",
                        key="web_server.send_button_label",
                    ),
                    locale,
                ),
            )
            .replace(
                "<!-- INPUT_CODE -->",
                self.translator.translate(
                    LocaleStr(
                        "Input the verification code you received in your email:",
                        key="web_server.input_code_label",
                    ),
                    locale,
                ),
            )
            .replace("<!-- USER_ID -->", str(payload.user_id))
            .replace("<!-- GUILD_ID -->", str(payload.guild_id) if payload.guild_id else "null")
            .replace("<!-- CHANNEL_ID -->", str(payload.channel_id))
            .replace("<!-- MESSAGE_ID -->", str(payload.message_id))
            .replace("<!-- LOCALE -->", locale.value)
        )

        return content

    async def captcha(self, request: web.Request) -> web.StreamResponse:
        payload = LoginNotifPayload.parse_from_request(request)
        body = await self._get_page("captcha", payload)
        return web.Response(body=body, content_type="text/html")

    async def verify_email(self, request: web.Request) -> web.StreamResponse:
        payload = LoginNotifPayload.parse_from_request(request)
        body = await self._get_page("verify-email", payload)
        return web.Response(body=body, content_type="text/html")

    async def gt(self, _: web.Request) -> web.StreamResponse:
        async with aiohttp.ClientSession() as session:
            r = await session.get(GT_URL)
            content = await r.read()

        return web.Response(body=content, content_type="text/javascript")

    async def mmt_endpoint(self, request: web.Request) -> web.Response:
        user_id = request.query["user_id"]
        mmt = await self._get_mmt(int(user_id))
        return web.json_response(mmt)

    async def send_data_endpoint(self, request: web.Request) -> web.Response:
        data: dict[str, Any] = await request.json()

        user_id = data.pop("user_id")
        await User.filter(id=int(user_id)).update(temp_data=data)
        conn = Tortoise.get_connection("default")
        await conn.execute_query(f"NOTIFY login, '{user_id}'")

        return web.Response(status=204)

    async def redirect(self, request: web.Request) -> web.Response:
        channel_id = request.query["channel_id"]
        guild_id = request.query["guild_id"]
        message_id = request.query["message_id"]

        protocol = (
            f"discord://-/channels/@me/{channel_id}/{message_id}"
            if guild_id == "null"
            else f"discord://-/channels/{guild_id}/{channel_id}/{message_id}"
        )
        return web.Response(status=302, headers={"Location": protocol})

    async def style_css(self, _: web.Request) -> web.StreamResponse:
        async with aiofiles.open("src/web_server/style.css", encoding="utf-8") as f:
            css = await f.read()

        return web.Response(
            body=css,
            content_type="text/css",
        )

    async def run(self, port: int = 5000) -> None:
        LOGGER_.info("Starting web server... (port=%d)", port)

        app = web.Application()
        app.add_routes(
            [
                web.get("/captcha", self.captcha),
                web.get("/verify-email", self.verify_email),
                web.get("/gt.js", self.gt),
                web.get("/mmt", self.mmt_endpoint),
                web.post("/send-data", self.send_data_endpoint),
                web.get("/style.css", self.style_css),
                web.get("/redirect", self.redirect),
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
