import asyncio
import logging

import aiofiles
import aiohttp
import genshin
from aiohttp import web
from discord import Locale
from genshin.errors import GenshinException
from genshin.utility import geetest

from hoyo_buddy.bot.translator import LocaleStr, Translator
from hoyo_buddy.db.models import User

log = logging.getLogger(__name__)


GT_URL = "https://raw.githubusercontent.com/GeeTeam/gt3-node-sdk/master/demo/static/libs/gt.js"


class GeetestWebServer:
    def __init__(self, translator: Translator) -> None:
        self.translator = translator

    @staticmethod
    async def _get_account_and_password(user_id: int) -> tuple[str, str, User]:
        user = await User.get_or_none(id=user_id)
        if user is None:
            raise web.HTTPNotFound(reason="User not found")

        email = user.temp_data.get("email")
        password = user.temp_data.get("password")
        if email is None or password is None:
            raise web.HTTPBadRequest(reason="Missing email or password")
        return email, password, user

    async def index(self, request: web.Request) -> web.StreamResponse:
        user_id = request.query.get("user_id")
        if user_id is None:
            return web.Response(status=400, reason="Missing user_id")
        locale = Locale(request.query.get("locale", "en-US"))
        loading_text = self.translator.translate(
            LocaleStr(
                "Loading CAPTCHA...",
                key="loading_captcha_text",
            ),
            locale,
        )
        button_label = self.translator.translate(
            LocaleStr("Click me to complete CAPTCHA", key="geetest_button_label"), locale
        )
        close_tab = self.translator.translate(
            LocaleStr(
                "You may now close this tab and go back to Discord.",
                key="geetest_finish_label",
            ),
            locale,
        )
        no_geetest_close_tab = self.translator.translate(
            LocaleStr(
                "You're lucky!<br>No CAPTCHA is needed, you may now close this tab and go back to Discord.",
                key="no_geetest_finish_label",
            ),
            locale,
        )

        async with aiofiles.open("hoyo_buddy/web_server/pages/index.html", encoding="utf-8") as f:
            index = await f.read()

        body = (
            index.replace("<!-- LOADING_TEXT -->", loading_text)
            .replace("<!-- BUTTON_LABEL -->", button_label)
            .replace("<!-- CLOSE_TAB -->", close_tab)
            .replace("<!-- USER_ID -->", user_id)
            .replace("<!-- NO_GEETEST_CLOSE_TAB -->", no_geetest_close_tab)
        )

        return web.Response(
            body=body,
            content_type="text/html",
        )

    @staticmethod
    async def gt(_: web.Request) -> web.StreamResponse:
        async with aiohttp.ClientSession() as session:
            r = await session.get(GT_URL)
            content = await r.read()

        return web.Response(body=content, content_type="text/javascript")

    async def mmt_endpoint(self, request: web.Request) -> web.Response:
        user_id = request.query.get("user_id")
        if user_id is None:
            return web.Response(status=400, reason="Missing user_id")
        account, password, _ = await self._get_account_and_password(int(user_id))

        mmt = await geetest.create_mmt(account, password)
        if mmt.get("data") is None:
            user = await User.get(id=int(user_id))
            user.temp_data["cookies"] = mmt
            user.temp_data.pop("email", None)
            user.temp_data.pop("password", None)
            return web.Response(status=400, reason="Failed to create mmt")

        return web.json_response(mmt)

    async def login(self, request: web.Request) -> web.Response:
        body = await request.json()
        user_id = body.get("user_id")
        if user_id is None:
            return web.Response(status=400, reason="Missing user_id")
        account, password, user = await self._get_account_and_password(int(user_id))

        try:
            data = await genshin.Client().login_with_geetest(
                account, password, body["sid"], body["gt"]
            )
        except GenshinException as e:
            user.temp_data["cookies"] = {"retcode": e.retcode, "message": e.msg}
        except Exception as e:  # skipcq: PYL-W0703
            user.temp_data["cookies"] = {"retcode": -1, "message": str(e)}
        else:
            user.temp_data["cookies"] = data

        user.temp_data.pop("email", None)
        user.temp_data.pop("password", None)
        await user.save()
        return web.json_response({})

    async def style_css(self, _: web.Request) -> web.StreamResponse:
        async with aiofiles.open("hoyo_buddy/web_server/pages/style.css", encoding="utf-8") as f:
            css = await f.read()

        return web.Response(
            body=css,
            content_type="text/css",
        )

    async def run(self, port: int = 5000) -> None:
        log.info("Starting web server... (port=%d)", port)
        app = web.Application()
        app.add_routes(
            [
                web.get("/", self.index),
                web.get("/gt.js", self.gt),
                web.get("/mmt", self.mmt_endpoint),
                web.post("/login", self.login),
                web.get("/style.css", self.style_css),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", port)
        await site.start()
        log.info("Web server started")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            log.info("Web server shutting down...")
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()
