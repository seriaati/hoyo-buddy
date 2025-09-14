from __future__ import annotations

import asyncio
import contextlib
import urllib.parse
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
import asyncpg
import flet as ft
import genshin
import orjson
from flet.core.client_storage import ClientStorage as ftClientStorage
from loguru import logger
from pydantic import ValidationError

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import WEB_APP_URLS, locale_to_gpy_lang
from hoyo_buddy.db import GachaHistory
from hoyo_buddy.enums import Game, Locale, Platform
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.utils import dict_cookie_to_str
from hoyo_buddy.utils.misc import get_project_version

from . import pages
from .login_handler import handle_action_ticket, handle_mobile_otp, handle_session_mmt
from .schema import GachaParams, Params
from .utils import (
    clear_storage,
    decrypt_string,
    encrypt_string,
    get_gacha_icon,
    get_gacha_names,
    refresh_page_view,
    show_error_banner,
    show_loading_snack_bar,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class ClientStorage(ftClientStorage):
    def __init__(self, page: ft.Page) -> None:
        super().__init__(page)

    async def remove_async(self, key: str) -> Any:
        with contextlib.suppress(TimeoutError):
            return await super().remove_async(key)

    async def get_async(self, key: str) -> Any:
        with contextlib.suppress(TimeoutError):
            return await super().get_async(key)

    async def set_async(self, key: str, value: Any) -> bool:
        with contextlib.suppress(TimeoutError):
            return await super().set_async(key, value)
        return False

    async def contains_key_async(self, key: str) -> bool:
        with contextlib.suppress(TimeoutError):
            return await super().contains_key_async(key)
        return False


class WebApp:
    def __init__(self, page: ft.Page) -> None:
        self._page = page
        self._page.on_route_change = self.on_route_change

    async def initialize(self) -> None:
        self._page.theme_mode = ft.ThemeMode.DARK
        self._page.go(self._page.route)

    async def on_route_change(self, e: ft.RouteChangeEvent) -> Any:
        page: ft.Page = e.page
        parsed = urllib.parse.urlparse(e.route)
        route = parsed.path

        parsed_params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        if "gacha" in route:
            view = await self._handle_gacha_routes(route, parsed_params)
            page.title = "GachaLog System"
            if view is not None:
                view.appbar = self.gacha_app_bar
        elif route == "/custom_oauth_callback":
            view = await self._handle_oauth(parsed_params)
        else:
            if route != "/login" and not page.session.contains_key("hb.user_id"):
                asyncio.create_task(page.client_storage.set_async("hb.original_route", e.route))
                locale = parsed_params.get("locale", "en-US")
                page.go(f"/login?locale={locale}")
                return

            view = await self._handle_routes(route, parsed_params)
            page.title = "Login System"
            if view is not None:
                view.appbar = self.login_app_bar

        if view is None:
            return

        refresh_page_view(page, view)

    def close_dialogs(self) -> None:
        controls = self._page._Page__offstage.controls  # pyright: ignore[reportAttributeAccessIssue]
        for control in controls:
            if isinstance(control, ft.AlertDialog):
                self._page.close(control)

    def close_banners(self) -> None:
        controls = self._page._Page__offstage.controls  # pyright: ignore[reportAttributeAccessIssue]
        for control in controls:
            if isinstance(control, ft.Banner):
                self._page.close(control)

    async def _handle_on_login(self, params: Params) -> ft.View | None:
        page = self._page

        encrypted_email, encrypted_password = await self._get_encrypted_email_password(
            page, params.user_id
        )
        if not encrypted_email or not encrypted_password:
            return pages.ErrorPage(
                code=400, message="Cannot find email or password in client storage."
            )

        mmt_result = await self._get_user_temp_data(params.user_id)
        email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

        device_id = await page.client_storage.get_async(f"hb.{params.user_id}.device_id")
        if device_id is None:
            return pages.ErrorPage(code=400, message="Cannot find device ID in client storage.")

        client = ProxyGenshinClient()
        try:
            result = await client._app_login(
                email,
                password,
                mmt_result=genshin.models.SessionMMTResult(**mmt_result),
                device_id=device_id,
                device_model="Hoyo Buddy",
                device_name=get_project_version(),
            )
        except Exception as exc:
            show_error_banner(page, message=str(exc))
            return None

        if isinstance(result, genshin.models.ActionTicket):
            # Email verification required
            try:
                email_result = await client._send_verification_email(result)
            except Exception as exc:
                show_error_banner(page, message=str(exc))
                return None

            if isinstance(email_result, genshin.models.SessionMMT):
                # Geetest triggered for sending email verification code
                logger.debug(f"[{params.user_id}] Saving action ticket to client storage")
                await page.client_storage.set_async(
                    f"hb.{params.user_id}.action_ticket", orjson.dumps(result.model_dump()).decode()
                )
                await handle_session_mmt(
                    email_result,
                    email=email,
                    password=password,
                    page=page,
                    params=params,
                    locale=Locale(params.locale),
                    mmt_type="on_email_send",
                )
            else:
                await handle_action_ticket(
                    result,
                    email=email,
                    password=password,
                    page=page,
                    params=params,
                    locale=Locale(params.locale),
                    device_id=device_id,
                )
        else:
            encrypted_cookies = encrypt_string(result.to_str())
            await page.client_storage.set_async(f"hb.{params.user_id}.cookies", encrypted_cookies)
            page.go(f"/finish?{params.to_query_string()}")

    async def _handle_on_email_send(self, params: Params) -> ft.View | None:
        page = self._page

        encrypted_email, encrypted_password = await self._get_encrypted_email_password(
            page, params.user_id
        )
        if not encrypted_email or not encrypted_password:
            return pages.ErrorPage(
                code=400, message="Cannot find email or password in client storage."
            )

        device_id = await page.client_storage.get_async(f"hb.{params.user_id}.device_id")
        if device_id is None:
            return pages.ErrorPage(code=400, message="Cannot find device ID in client storage.")

        str_action_ticket: str | None = await page.client_storage.get_async(
            f"hb.{params.user_id}.action_ticket"
        )
        if str_action_ticket is None:
            return pages.ErrorPage(code=400, message="Cannot find action ticket in client storage.")

        action_ticket = genshin.models.ActionTicket(**orjson.loads(str_action_ticket.encode()))
        email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

        await handle_action_ticket(
            action_ticket,
            email=email,
            password=password,
            page=page,
            params=params,
            locale=Locale(params.locale),
            device_id=device_id,
        )

    async def _handle_on_otp_send(self, params: Params) -> ft.View | None:
        page = self._page

        encrypted_mobile = await page.client_storage.get_async(f"hb.{params.user_id}.mobile")
        if encrypted_mobile is None:
            return pages.ErrorPage(code=400, message="Cannot find mobile number in client storage.")

        mobile = decrypt_string(encrypted_mobile)
        client = ProxyGenshinClient(region=genshin.Region.CHINESE)
        mmt_result = await self._get_user_temp_data(params.user_id)
        try:
            await client._send_mobile_otp(
                mobile, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
            )
        except Exception as exc:
            show_error_banner(page, message=str(exc))
            return None

        handle_mobile_otp(mobile=mobile, page=page, params=params)

    async def _handle_geetest(self, params: Params, locale: Locale) -> ft.View | None:
        page = self._page

        self.close_dialogs()
        show_loading_snack_bar(page, locale=locale)

        gt_type: Literal[
            "on_login", "on_email_send", "on_otp_send"
        ] = await page.client_storage.get_async(f"hb.{params.user_id}.gt_type")  # pyright: ignore[reportAssignmentType]
        logger.debug(f"[{params.user_id}] Handling geetest type: {gt_type}")

        if gt_type == "on_login":
            return await self._handle_on_login(params)
        if gt_type == "on_email_send":
            return await self._handle_on_email_send(params)
        if gt_type == "on_otp_send":
            return await self._handle_on_otp_send(params)

        return pages.ErrorPage(
            code=400, message=f"Invalid geetest type {gt_type} in client storage."
        )

    async def _get_encrypted_email_password(
        self, page: ft.Page, user_id: int
    ) -> tuple[str | None, str | None]:
        encrypted_email: str | None = await page.client_storage.get_async(f"hb.{user_id}.email")
        encrypted_password: str | None = await page.client_storage.get_async(
            f"hb.{user_id}.password"
        )
        return encrypted_email, encrypted_password

    async def _get_user_temp_data(self, user_id: int) -> dict[str, Any]:
        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            mmt_result: str = await conn.fetchval(
                'SELECT temp_data FROM "user" WHERE id = $1', user_id
            )
        finally:
            await conn.close()
        return orjson.loads(mmt_result)

    async def _get_or_create_device_id(self, page: ft.Page, user_id: int) -> str:
        device_id = await page.client_storage.get_async(f"hb.{user_id}.device_id")
        logger.debug(f"[{user_id}] Device ID: {device_id}")
        if device_id is None:
            logger.debug(f"[{user_id}] Device ID not found, generating a new one.")
            device_id = genshin.Client.generate_app_device_id()
            await page.client_storage.set_async(f"hb.{user_id}.device_id", device_id)

        return device_id

    async def _handle_finish(self, params: Params, locale: Locale) -> ft.View | None:
        logger.debug(f"[{params.user_id}] Handle finish start")
        page = self._page

        self.close_dialogs()
        self.close_banners()

        view = pages.LoadingPage(
            title=LocaleStr(key="fetching_accounts"),
            description=LocaleStr(key="fetching_accounts_stuck"),
            locale=locale,
        )
        refresh_page_view(page, view, app_bar=self.login_app_bar)

        device_id_exists = await page.client_storage.contains_key_async(
            f"hb.{params.user_id}.device_id"
        )
        device_fp_exists = await page.client_storage.contains_key_async(
            f"hb.{params.user_id}.device_fp"
        )
        if params.platform is Platform.MIYOUSHE and (not device_id_exists or not device_fp_exists):
            page.go(f"/device_info?{params.to_query_string()}")
            return None

        encrypted_cookies = await page.client_storage.get_async(f"hb.{params.user_id}.cookies")
        if encrypted_cookies is None:
            return pages.ErrorPage(code=400, message="Cannot find cookies in client storage.")

        cookies = decrypt_string(encrypted_cookies)
        fetch_cookie = (
            params.platform is Platform.HOYOLAB and "stoken" in cookies and "ltmid_v2" in cookies
        )
        logger.debug(f"[{params.user_id}] Fetch cookie with stoken: {fetch_cookie}")
        if fetch_cookie:
            # Get ltoken_v2 and cookie_token_v2
            try:
                new_dict_cookie = await genshin.fetch_cookie_with_stoken_v2(
                    cookies, token_types=[2, 4]
                )
            except Exception as exc:
                logger.exception(f"[{params.user_id}] Fetch cookie with stoken error: {exc}")
                show_error_banner(page, message=str(exc))
                return None

            dict_cookie = genshin.parse_cookie(cookies)
            dict_cookie.update(new_dict_cookie)
            cookies = dict_cookie_to_str(dict_cookie)

        device_id = await page.client_storage.get_async(f"hb.{params.user_id}.device_id")
        device_fp = await page.client_storage.get_async(f"hb.{params.user_id}.device_fp")

        logger.debug(f"[{params.user_id}] Before get game accs, cookies: {cookies}")
        if device_id is not None:
            logger.debug(f"[{params.user_id}] Before get game accs, device id: {device_id}")
        if device_fp is not None:
            logger.debug(f"[{params.user_id}] Before get game accs, device fp: {device_fp}")

        try:
            platform = params.platform or Platform.HOYOLAB
            client = ProxyGenshinClient(
                cookies,
                lang=locale_to_gpy_lang(locale),
                region=genshin.Region.OVERSEAS
                if platform is Platform.HOYOLAB
                else genshin.Region.CHINESE,
                device_id=device_id,
                device_fp=device_fp,
            )
            accounts = await client.get_game_accounts()
        except Exception as exc:
            show_error_banner(page, message=str(exc))
            return None

        if not accounts:
            return pages.ErrorPage(
                code=404,
                message=LocaleStr(
                    key="no_game_accounts_error_message",
                    platform=EnumStr(params.platform or Platform.HOYOLAB),
                ).translate(locale),
            )

        return pages.FinishPage(
            params=params,
            locale=locale,
            accounts=accounts,
            cookies=cookies,
            device_id=device_id,
            device_fp=device_fp,
        )

    async def _handle_routes(self, route: str, parsed_params: dict[str, str]) -> ft.View | None:
        page = self._page
        locale = parsed_params.get("locale", "en-US")

        if route == "/login":
            user_data = await self.fetch_user_data()
            try:
                locale_ = Locale(locale)
            except ValueError:
                return pages.ErrorPage(code=422, message="Invalid locale")

            return pages.LoginPage(user_data, locale=locale_)

        if route == "/geetest":
            if "user_id" not in parsed_params:
                return pages.ErrorPage(code=400, message="Missing user_id in parameters.")

            query: str | None = await page.client_storage.get_async(
                f"hb.{parsed_params['user_id']}.params"
            )
            if query is None:
                return pages.ErrorPage(code=400, message="Cannot find params in client storage.")

            parsed_params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

        user_id = page.session.get("hb.user_id")
        if user_id is None:
            return pages.ErrorPage(code=400, message="Cannot find user_id in client storage.")
        parsed_params["user_id"] = user_id

        try:
            params = Params(**parsed_params)  # pyright: ignore[reportArgumentType]
            locale = Locale(params.locale)
        except (ValidationError, ValueError):
            view = pages.ErrorPage(code=422, message="Invalid parameters")
        else:
            match route:
                case "/platforms":
                    clear_storage(page, user_id=params.user_id)
                    view = pages.PlatformsPage(params=params, locale=locale)
                case "/methods":
                    view = pages.MethodsPage(params=params, locale=locale)
                case "/email_password":
                    device_id = await self._get_or_create_device_id(page, user_id)
                    view = pages.EmailPasswordPage(
                        params=params, locale=locale, device_id=device_id
                    )
                case "/dev_tools":
                    view = pages.DevToolsPage(params=params, locale=locale)
                case "/dev":
                    view = pages.DevModePage(params=params, locale=locale)
                case "/mod_app":
                    view = pages.ModAppPage(params=params)
                case "/mobile":
                    view = pages.MobilePage(params=params)
                case "/qrcode":
                    view = pages.QRCodePage(params=params)
                case "/device_info":
                    view = pages.DeviceInfoPage(params=params)
                case "/finish":
                    view = await self._handle_finish(params, locale)
                case "/geetest":
                    view = await self._handle_geetest(params, locale)
                case _:
                    view = pages.ErrorPage(code=404, message="Not Found")

        return view

    async def _handle_gacha_routes(
        self, route: str, parsed_params: dict[str, str]
    ) -> ft.View | None:
        page = self._page

        try:
            params = GachaParams(**parsed_params)  # pyright: ignore[reportArgumentType]
            locale = Locale(params.locale)
        except (ValidationError, ValueError):
            return pages.ErrorPage(code=422, message="Invalid parameters")

        match route:
            case "/gacha_log":
                account_exists = await self._check_account_exists(params.account_id)
                if not account_exists:
                    return pages.ErrorPage(code=404, message="Account not found")

                total_row = await self._get_gacha_log_row_num(params)
                gacha_logs = await self._get_gacha_logs(params)

                gacha_icons = await self._get_gacha_icons(gacha_logs)
                asyncio.create_task(page.client_storage.set_async("hb.gacha_icons", gacha_icons))

                game = await self._get_account_game(params.account_id)

                if params.name_contains:
                    gacha_names = await get_gacha_names(
                        self._page, gachas=gacha_logs, locale=locale, game=game
                    )
                    gacha_logs = [
                        g
                        for g in gacha_logs
                        if params.name_contains in gacha_names[g.item_id].lower()
                    ][(params.page - 1) * params.size : params.page * params.size]

                view = pages.GachaLogPage(
                    locale=locale,
                    gacha_histories=gacha_logs,
                    gacha_icons=gacha_icons,
                    game=game,
                    params=params,
                    max_page=(total_row + params.size - 1) // params.size,
                )
            case _:
                view = pages.ErrorPage(code=404, message="Not Found")

        return view

    @staticmethod
    async def _get_account_game(account_id: int) -> Game:
        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            game = await conn.fetchval('SELECT game FROM "hoyoaccount" WHERE id = $1', account_id)
            return Game(game)
        finally:
            await conn.close()

    @staticmethod
    async def _get_gacha_log_row_num(params: GachaParams) -> int:
        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            return await conn.fetchval(
                'SELECT COUNT(*) FROM "gachahistory" WHERE account_id = $1 AND banner_type = $2 AND rarity = ANY($3)',
                params.account_id,
                params.banner_type,
                params.rarities,
            )
        finally:
            await conn.close()

    @staticmethod
    async def _check_account_exists(account_id: int) -> bool:
        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            return await conn.fetchval(
                'SELECT EXISTS(SELECT 1 FROM "hoyoaccount" WHERE id = $1)', account_id
            )
        finally:
            await conn.close()

    @staticmethod
    async def _get_gacha_logs(params: GachaParams) -> list[GachaHistory]:
        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            if params.name_contains:
                rows = await conn.fetch(
                    'SELECT * FROM "gachahistory" WHERE account_id = $1 AND banner_type = $2 AND rarity = ANY($3) ORDER BY wish_id DESC',
                    params.account_id,
                    params.banner_type,
                    params.rarities,
                )
            else:
                rows = await conn.fetch(
                    'SELECT * FROM "gachahistory" WHERE account_id = $1 AND banner_type = $2 AND rarity = ANY($3) ORDER BY wish_id DESC LIMIT $4 OFFSET $5',
                    params.account_id,
                    params.banner_type,
                    params.rarities,
                    params.size,
                    (params.page - 1) * params.size,
                )
            return [GachaHistory(**row) for row in rows]
        finally:
            await conn.close()

    async def _get_gacha_icons(self, gachas: Sequence[GachaHistory]) -> dict[int, str]:
        cached_gacha_icons: dict[str, str] = (
            await self._page.client_storage.get_async("hb.gacha_icons") or {}
        )
        result: dict[int, str] = {}
        for gacha in gachas:
            if str(gacha.item_id) in cached_gacha_icons:
                result[gacha.item_id] = cached_gacha_icons[str(gacha.item_id)]
            else:
                result[gacha.item_id] = await get_gacha_icon(game=gacha.game, item_id=gacha.item_id)
                cached_gacha_icons[str(gacha.item_id)] = result[gacha.item_id]

        asyncio.create_task(self._page.client_storage.set_async("gacha_icons", cached_gacha_icons))
        return result

    async def fetch_user_data(self) -> dict[str, Any] | None:
        page = self._page
        access_token = await page.client_storage.get_async("hb.oauth_access_token")
        if access_token is None:
            return None

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp,
        ):
            if resp.status != 200:
                refresh_token = await page.client_storage.get_async("hb.oauth_refresh_token")
                if refresh_token is None:
                    return None

                async with session.post(
                    "https://discord.com/api/oauth2/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": CONFIG.discord_client_id,
                        "client_secret": CONFIG.discord_client_secret,
                    },
                ) as refresh_resp:
                    if refresh_resp.status != 200:
                        return None

                    data = await refresh_resp.json()
                    access_token = data.get("access_token")

                    if access_token is None:
                        return None

                    await page.client_storage.set_async("hb.oauth_access_token", access_token)

                return await self.fetch_user_data()

            return await resp.json()

    async def _handle_oauth(self, params: dict[str, str]) -> ft.View | None:
        page = self._page

        state = await page.client_storage.get_async("hb.oauth_state")
        if state != params.get("state"):
            return pages.ErrorPage(code=403, message="Invalid state")

        code = params.get("code")
        if code is None:
            return pages.ErrorPage(code=400, message="Missing code")

        show_loading_snack_bar(page)

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CONFIG.discord_client_id,
                    "client_secret": CONFIG.discord_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{WEB_APP_URLS[CONFIG.env]}/custom_oauth_callback",
                    "scope": "identify",
                },
            ) as resp,
        ):
            if resp.status != 200:
                return pages.ErrorPage(
                    code=resp.status, message=resp.reason or "Failed to get access token"
                )
            data: dict[str, Any] = await resp.json()

        access_token = data.get("access_token")
        if access_token is None:
            return pages.ErrorPage(code=400, message="Missing access token")

        refresh_token = data.get("refresh_token")
        if refresh_token is None:
            return pages.ErrorPage(code=400, message="Missing refresh token")

        await page.client_storage.set_async("hb.oauth_access_token", access_token)
        await page.client_storage.set_async("hb.oauth_refresh_token", refresh_token)

        user_data = await self.fetch_user_data()
        if user_data is None:
            return pages.ErrorPage(code=400, message="Failed to fetch user data")

        user_id = user_data.get("id")
        if user_id is None:
            return pages.ErrorPage(code=400, message="Missing user ID")

        page.session.set("hb.user_id", int(user_id))

        original_route = await page.client_storage.get_async("hb.original_route")
        if original_route is None:
            return page.go("/platforms")

        asyncio.create_task(page.client_storage.remove_async("hb.original_route"))
        return page.go(original_route)

    @property
    def login_app_bar(self) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Row(
                [
                    ft.Image(src="/images/logo.png", width=32, height=32),
                    ft.Container(ft.Text("Login System"), margin=ft.margin.only(left=4)),
                ]
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.IconButton(ft.Icons.QUESTION_MARK, url="https://discord.com/invite/ryfamUykRw")
            ],
        )

    @property
    def gacha_app_bar(self) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Row(
                [
                    ft.Image(src="/images/logo.png", width=32, height=32),
                    ft.Container(ft.Text("GachaLog System"), margin=ft.margin.only(left=4)),
                ]
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            actions=[
                ft.IconButton(ft.Icons.QUESTION_MARK, url="https://discord.com/invite/ryfamUykRw")
            ],
        )
