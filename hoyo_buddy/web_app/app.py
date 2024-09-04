from __future__ import annotations

import os
import urllib.parse
from typing import TYPE_CHECKING, Any, Literal

import asyncpg
import flet as ft
import genshin
import orjson
from discord import Locale
from pydantic import ValidationError

from hoyo_buddy.web_app.pages.error import ErrorPage

from ..constants import locale_to_gpy_lang
from ..enums import Platform
from ..utils import dict_cookie_to_str, str_cookie_to_dict
from ..web_app.login_handler import handle_action_ticket, handle_session_mmt
from ..web_app.utils import decrypt_string, encrypt_string
from . import pages
from .schema import Params

if TYPE_CHECKING:
    from ..l10n import Translator


class WebApp:
    def __init__(self, page: ft.Page, *, translator: Translator) -> None:
        self._page = page
        self._translator = translator
        self._page.on_route_change = self.on_route_change

    async def initialize(self) -> None:
        self._page.title = "Hoyo Buddy Login System"
        await self._page.go_async(self._page.route)

    async def on_route_change(self, e: ft.RouteChangeEvent) -> Any:
        page: ft.Page = e.page
        parsed = urllib.parse.urlparse(e.route)
        route = parsed.path
        parsed_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        try:
            params = Params(**parsed_params)  # pyright: ignore[reportArgumentType]
            locale = Locale(params.locale)
        except (ValidationError, ValueError):
            view = pages.ErrorPage(code=422, message="Invalid parameters")
        else:
            match route:
                case "/platforms":
                    view = pages.PlatformsPage(
                        params=params, translator=self._translator, locale=locale
                    )
                case "/methods":
                    view = pages.MethodsPage(
                        params=params, translator=self._translator, locale=locale
                    )
                case "/email_password":
                    view = pages.EmailPasswordPage(
                        params=params, translator=self._translator, locale=locale
                    )
                case "/dev_tools":
                    view = pages.DevToolsPage(
                        params=params, translator=self._translator, locale=locale
                    )
                case "/javascript":
                    view = pages.JavascriptPage(
                        params=params, translator=self._translator, locale=locale
                    )
                case "/mod_app":
                    view = pages.ModAppPage(params=params)
                case "/mobile":
                    view = pages.MobilePage(params=params)
                case "/finish":
                    view = await self._handle_finish(page, params, locale)
                case "/geetest":
                    view = await self._handle_geetest(page, params)
                    if view is None:
                        return
                case _:
                    view = pages.ErrorPage(code=404, message="Not Found")

        view.appbar = self.app_bar
        view.scroll = ft.ScrollMode.AUTO

        page.views.clear()
        page.views.append(view)
        await page.update_async()

    async def _handle_geetest(self, page: ft.Page, params: Params) -> ft.View | None:
        gt_type: Literal["on_login", "on_send_email"] = await page.client_storage.get_async(
            f"hb.{params.user_id}.gt_type"
        )  # pyright: ignore[reportAssignmentType]
        if gt_type == "on_login":
            encrypted_email, encrypted_password = await self._get_encrypted_email_password(
                page, params.user_id
            )
            if not encrypted_email or not encrypted_password:
                return ErrorPage(
                    code=400, message="Cannot find email or password in client storage."
                )

            mmt_result = await self._get_user_temp_data(params.user_id)
            email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

            client = genshin.Client()
            result = await client._app_login(
                email, password, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
            )
            if isinstance(result, genshin.models.ActionTicket):
                # Email verification required
                email_result = await client._send_verification_email(result)
                if isinstance(email_result, genshin.models.SessionMMT):
                    # Geetest triggered for sending email verification code
                    await page.client_storage.set_async(
                        f"hb.{params.user_id}.gt_type", "on_email_send"
                    )
                    await page.client_storage.set_async(
                        f"hb.{params.user_id}.action_ticket", orjson.dumps(result.dict()).decode()
                    )
                    await handle_session_mmt(
                        email_result,
                        email=email,
                        password=password,
                        page=page,
                        params=params,
                        translator=self._translator,
                        locale=Locale(params.locale),
                        on_email_send=True,
                    )
                else:
                    await handle_action_ticket(
                        result,
                        email=email,
                        password=password,
                        page=page,
                        params=params,
                        translator=self._translator,
                        locale=Locale(params.locale),
                    )
            else:
                encrypted_cookies = encrypt_string(result.to_str())
                await page.client_storage.set_async(
                    f"hb.{params.user_id}.cookies", encrypted_cookies
                )
                await page.go_async(f"/finish?{params.to_query_string()}")
        else:
            encrypted_email, encrypted_password = await self._get_encrypted_email_password(
                page, params.user_id
            )
            if not encrypted_email or not encrypted_password:
                return ErrorPage(
                    code=400, message="Cannot find email or password in client storage."
                )

            str_action_ticket: str | None = await page.client_storage.get_async(
                f"hb.{params.user_id}.action_ticket"
            )
            if str_action_ticket is None:
                return ErrorPage(code=400, message="Cannot find action ticket in client storage.")
            action_ticket = genshin.models.ActionTicket(**orjson.loads(str_action_ticket.encode()))
            mmt_result = await self._get_user_temp_data(params.user_id)
            email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

            client = genshin.Client()
            await client._send_verification_email(
                action_ticket, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
            )
            await handle_action_ticket(
                action_ticket,
                email=email,
                password=password,
                page=page,
                params=params,
                translator=self._translator,
                locale=Locale(params.locale),
            )

        return None

    async def _get_encrypted_email_password(
        self, page: ft.Page, user_id: int
    ) -> tuple[str | None, str | None]:
        encrypted_email: str | None = await page.client_storage.get_async(f"hb.{user_id}.email")
        encrypted_password: str | None = await page.client_storage.get_async(
            f"hb.{user_id}.password"
        )
        return encrypted_email, encrypted_password

    async def _get_user_temp_data(self, user_id: int) -> dict[str, Any]:
        conn = await asyncpg.connect(os.environ["DB_URL"])
        try:
            mmt_result: str = await conn.fetchval(
                "SELECT temp_data FROM user WHERE id = $1", user_id
            )
        finally:
            await conn.close()
        return orjson.loads(mmt_result)

    async def _handle_finish(self, page: ft.Page, params: Params, locale: Locale) -> ft.View:
        encrypted_cookies = await page.client_storage.get_async(f"hb.{params.user_id}.cookies")

        if encrypted_cookies is None:
            view = pages.ErrorPage(code=400, message="Cannot find cookies in client storage.")
        else:
            cookies = decrypt_string(encrypted_cookies)
            if params.platform is Platform.HOYOLAB and (
                "stoken" in cookies or "stoken_v2" in cookies
            ):
                # Get ltoken_v2 and cookie_token_v2
                new_dict_cookie = await genshin.fetch_cookie_with_stoken_v2(
                    cookies, token_types=[2, 4]
                )
                dict_cookie = str_cookie_to_dict(cookies)
                dict_cookie.update(new_dict_cookie)
                cookies = dict_cookie_to_str(dict_cookie)

            device_id = await page.client_storage.get_async(f"hb.{params.user_id}.device_id")
            device_fp = await page.client_storage.get_async(f"hb.{params.user_id}.device_fp")

            client = genshin.Client(
                cookies,
                lang=locale_to_gpy_lang(locale),
                region=genshin.Region.OVERSEAS
                if params.platform is Platform.HOYOLAB
                else genshin.Region.CHINESE,
                device_id=device_id,
                device_fp=device_fp,
            )
            accounts = await client.get_game_accounts()
            view = pages.FinishPage(
                params=params,
                translator=self._translator,
                locale=locale,
                accounts=accounts,
                cookies=encrypted_cookies,
                device_id=device_id,
                device_fp=device_fp,
            )

        return view

    @property
    def app_bar(self) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Text("Hoyo Buddy Login System"), bgcolor=ft.colors.SURFACE_VARIANT
        )
