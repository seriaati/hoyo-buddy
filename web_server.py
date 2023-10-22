import asyncio
from typing import Tuple

import aiohttp
import genshin
from aiohttp import web
from discord import Locale
from dotenv import load_dotenv
from genshin.errors import GenshinException, raise_for_retcode
from genshin.utility import geetest

from hoyo_buddy.bot.translator import Translator
from hoyo_buddy.db.models import User

load_dotenv()

INDEX = """
<!DOCTYPE html>
<html>
  <body>
	<button hidden type="button" id="login">{button_label}</button>
  </body>
  <script src="./gt.js"></script>
  <script>
	fetch("/mmt?user_id={user_id}")
	  .then((response) => response.json())
	  .then((mmt) =>
		window.initGeetest(
		  {
			gt: mmt.data.gt,
			challenge: mmt.data.challenge,
			new_captcha: mmt.data.new_captcha,
			api_server: "api-na.geetest.com",
			lang: "en",
			product: "bind",
			https: false,
		  },
		  (captcha) => {
			captcha.appendTo("login");
			document.getElementById("login").hidden = false;
			captcha.onSuccess(() => {
			  fetch("/login", {
				method: "POST",
				body: JSON.stringify({
				  sid: mmt.session_id,
				  gt: captcha.getValidate(),
				  user_id: {user_id}
				}),
			  });
			  document.body.innerHTML = "{close_tab}";
			});
			document.getElementById("login").onclick = () => {
			  return captcha.verify();
			};
		  }
		)
	  );
  </script>
</html>
"""

GT_URL = "https://raw.githubusercontent.com/GeeTeam/gt3-node-sdk/master/demo/static/libs/gt.js"


class GeetestWebServer:
    def __init__(self):
        self.translator = Translator()

    @staticmethod
    async def _get_account_and_password(user_id: int) -> Tuple[str, str, User]:
        user = await User.get(id=user_id)
        return user.temp_data["account"], user.temp_data["password"], user

    async def index(self, request: web.Request) -> web.StreamResponse:
        user_id = request.query.get("user_id")
        if user_id is None:
            return web.Response(status=400, reason="Missing user_id")
        locale = Locale(request.query.get("locale", "en-US"))
        button_label = await self.translator.translate("Login", locale)
        close_tab = await self.translator.translate(
            "You may now close this tab.", locale
        )
        return web.Response(
            body=INDEX.format(
                user_id=user_id, button_label=button_label, close_tab=close_tab
            ),
            content_type="text/html",
        )

    async def gt(self, _: web.Request) -> web.StreamResponse:
        async with aiohttp.ClientSession() as session:
            r = await session.get(GT_URL)
            content = await r.read()

        return web.Response(body=content, content_type="text/javascript")

    async def mmt_endpoint(self, request: web.Request) -> web.Response:
        account, password, _ = await self._get_account_and_password(
            int(request.query["user_id"])
        )
        mmt = await geetest.create_mmt(account, password)
        if mmt["data"] is None:
            raise_for_retcode(mmt)  # type: ignore

        return web.json_response(mmt)

    async def login(self, request: web.Request) -> web.Response:
        body = await request.json()
        user_id = body["user_id"]
        account, password, user = await self._get_account_and_password(int(user_id))

        try:
            data = genshin.Client().login_with_geetest(
                account, password, body["sid"], body["gt"]
            )
        except GenshinException as e:
            user.temp_data["cookies"] = {"retcode": e.retcode, "message": e.msg}
        except Exception as e:  # skipcq: PYL-W0703
            user.temp_data["cookies"] = {"retcode": -1, "message": str(e)}
        else:
            user.temp_data["cookies"] = data

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
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.translator.unload()
            await site.stop()
            await runner.shutdown()
            await runner.cleanup()
            await app.shutdown()
            await app.cleanup()


async def main():
    server = GeetestWebServer()
    await server.run()


asyncio.run(main())
