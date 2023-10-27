import asyncio
import os
from typing import Tuple

import aiohttp
import genshin
from aiohttp import web
from discord import Locale
from discord.app_commands import locale_str as _T
from dotenv import load_dotenv
from genshin.errors import GenshinException
from genshin.utility import geetest
from tortoise.exceptions import DoesNotExist

from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db import Database
from hoyo_buddy.db.models import User

load_dotenv()

INDEX = """
<!DOCTYPE html>
<html>
  <head>
  <meta charset="UTF-8">
  <title>Geetest Web Server</title>
  <style>
    body {{
        background-color: #36393f;
        color: #dcddde;
        font-family: Whitney,Helvetica Neue,Helvetica,Arial,sans-serif;
        font-size: 64px;
        line-height: 1.5;
        margin: 0;
        padding: 0;
        height: 100vh;
        align-items: center;
        display: flex;
        justify-content: center;
    }}
    button {{
        background-color: #7289da;
        border: none;
        border-radius: 3px;
        color: #fff;
        cursor: pointer;
        display: block;
        font-size: 64px;
        font-weight: 500;
        height: 400px;
        margin: 0 auto;
        padding: 0;
        position: relative;
        text-align: center;
        transition: background-color .17s ease,border-color .17s ease,color .17s ease,box-shadow .17s ease;
        user-select: none;
        width: 800px;
    }}
    button:hover {{
        background-color: #677bc4;
    }}
    button:active {{
        background-color: #5b6eae;
    }}
  </style>
  </head>
  <body>
  <button hidden type="button" id="login">{button_label}</button>
  </body>
  <script src="./gt.js"></script>
  <script>
	fetch("/mmt?user_id={user_id}")
	  .then((response) => response.json())
	  .then((mmt) =>
		window.initGeetest(
		  {{
			gt: mmt.data.gt,
			challenge: mmt.data.challenge,
			new_captcha: mmt.data.new_captcha,
			api_server: "api-na.geetest.com",
			lang: "en",
			product: "bind",
			https: false,
		  }},
		  (captcha) => {{
			captcha.appendTo("login");
			document.getElementById("login").hidden = false;
			captcha.onSuccess(() => {{
			  fetch("/login", {{
				method: "POST",
				body: JSON.stringify({{
				  sid: mmt.session_id,
				  gt: captcha.getValidate(),
				  user_id: '{user_id}'
				}}),
			  }});
			  document.body.innerHTML = "{close_tab}";
			}});
			document.getElementById("login").onclick = () => {{
			  return captcha.verify();
			}};
		  }}
		)
	  );
  </script>
</html>
"""


GT_URL = "https://raw.githubusercontent.com/GeeTeam/gt3-node-sdk/master/demo/static/libs/gt.js"


class GeetestWebServer:
    def __init__(self):
        env = os.environ["ENV"]
        self.translator = Translator(env)

    @staticmethod
    async def _get_account_and_password(user_id: int) -> Tuple[str, str, User]:
        try:
            user = await User.get(id=user_id)
        except DoesNotExist:
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
        button_label = self.translator.translate(
            _T("Click me to complete CAPTCHA", key="geetest_button_label"), locale
        )
        close_tab = self.translator.translate(
            _T(
                "You may now close this tab and go back to Discord.",
                key="geetest_finish_label",
            ),
            locale,
        )

        body = INDEX.format(
            user_id=user_id, button_label=button_label, close_tab=close_tab
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

    async def run(self, port: int = 5000) -> None:
        await self.translator.load()
        app = web.Application()
        app.add_routes(
            [
                web.get("/", self.index),
                web.get("/gt.js", self.gt),
                web.get("/mmt", self.mmt_endpoint),
                web.post("/login", self.login),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", port)
        await site.start()

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.translator.unload()
            await site.stop()
            await app.shutdown()
            await app.cleanup()
            await runner.shutdown()
            await runner.cleanup()


async def main():
    async with Database(os.getenv("DATABASE_URL")):
        server = GeetestWebServer()
        await server.run()


asyncio.run(main())
