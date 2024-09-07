from __future__ import annotations

import asyncio
import os
import urllib.parse
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
import asyncpg
import flet as ft
import genshin
import orjson
from discord import Locale
from pydantic import ValidationError

from hoyo_buddy.constants import locale_to_gpy_lang, locale_to_zenless_data_lang
from hoyo_buddy.db.models import GachaHistory
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.utils import dict_cookie_to_str, get_gacha_icon, item_id_to_name, str_cookie_to_dict

from . import pages
from .login_handler import handle_action_ticket, handle_mobile_otp, handle_session_mmt
from .schema import GachaParams, Params
from .utils import (
    decrypt_string,
    encrypt_string,
    reset_storage,
    show_error_banner,
    show_loading_snack_bar,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..l10n import Translator


class WebApp:
    def __init__(self, page: ft.Page, *, translator: Translator) -> None:
        self._page = page
        self._translator = translator
        self._page.on_route_change = self.on_route_change

    async def initialize(self) -> None:
        self._page.theme_mode = ft.ThemeMode.DARK
        await self._page.go_async(self._page.route)

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
        else:
            view = await self._handle_login_routes(route, parsed_params)
            page.title = "Login System"
            if view is not None:
                view.appbar = self.login_app_bar

        if view is None:
            return

        view.scroll = ft.ScrollMode.AUTO

        page.views.clear()
        page.views.append(view)
        await page.update_async()

    async def _handle_geetest(self, params: Params, locale: Locale) -> ft.View | None:
        page = self._page
        translator = self._translator

        await page.close_dialog_async()
        await show_loading_snack_bar(page, translator=translator, locale=locale)

        gt_type: Literal[
            "on_login", "on_email_send", "on_otp_send"
        ] = await page.client_storage.get_async(f"hb.{params.user_id}.gt_type")  # pyright: ignore[reportAssignmentType]

        if gt_type == "on_login":
            encrypted_email, encrypted_password = await self._get_encrypted_email_password(
                page, params.user_id
            )
            if not encrypted_email or not encrypted_password:
                return pages.ErrorPage(
                    code=400, message="Cannot find email or password in client storage."
                )

            mmt_result = await self._get_user_temp_data(params.user_id)
            email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

            client = genshin.Client()
            try:
                result = await client._app_login(
                    email, password, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
                )
            except Exception as exc:
                await show_error_banner(page, message=str(exc))
                return None

            if isinstance(result, genshin.models.ActionTicket):
                # Email verification required
                try:
                    email_result = await client._send_verification_email(result)
                except Exception as exc:
                    await show_error_banner(page, message=str(exc))
                    return None

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
                        mmt_type="on_email_send",
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
        elif gt_type == "on_email_send":
            encrypted_email, encrypted_password = await self._get_encrypted_email_password(
                page, params.user_id
            )
            if not encrypted_email or not encrypted_password:
                return pages.ErrorPage(
                    code=400, message="Cannot find email or password in client storage."
                )

            str_action_ticket: str | None = await page.client_storage.get_async(
                f"hb.{params.user_id}.action_ticket"
            )
            if str_action_ticket is None:
                return pages.ErrorPage(
                    code=400, message="Cannot find action ticket in client storage."
                )
            action_ticket = genshin.models.ActionTicket(**orjson.loads(str_action_ticket.encode()))
            mmt_result = await self._get_user_temp_data(params.user_id)
            email, password = decrypt_string(encrypted_email), decrypt_string(encrypted_password)

            client = genshin.Client()
            try:
                await client._send_verification_email(
                    action_ticket, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
                )
            except Exception as exc:
                await show_error_banner(page, message=str(exc))
                return None

            await handle_action_ticket(
                action_ticket,
                email=email,
                password=password,
                page=page,
                params=params,
                translator=self._translator,
                locale=Locale(params.locale),
            )
        else:  # on_otp_send
            encrypted_mobile = await page.client_storage.get_async(f"hb.{params.user_id}.mobile")
            if encrypted_mobile is None:
                return pages.ErrorPage(
                    code=400, message="Cannot find mobile number in client storage."
                )

            mobile = decrypt_string(encrypted_mobile)
            client = genshin.Client(region=genshin.Region.CHINESE)
            mmt_result = await self._get_user_temp_data(params.user_id)
            try:
                await client._send_mobile_otp(
                    mobile, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
                )
            except Exception as exc:
                await show_error_banner(page, message=str(exc))
                return None

            await handle_mobile_otp(mobile=mobile, page=page, params=params)

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
                'SELECT temp_data FROM "user" WHERE id = $1', user_id
            )
        finally:
            await conn.close()
        return orjson.loads(mmt_result)

    async def _handle_finish(self, params: Params, locale: Locale) -> ft.View | None:
        page = self._page
        translator = self._translator

        await page.close_dialog_async()
        await page.close_banner_async()

        device_id_exists = await page.client_storage.contains_key_async(
            f"hb.{params.user_id}.device_id"
        )
        device_fp_exists = await page.client_storage.contains_key_async(
            f"hb.{params.user_id}.device_fp"
        )
        if params.platform is Platform.MIYOUSHE and (not device_id_exists or not device_fp_exists):
            await page.go_async(f"/device_info?{params.to_query_string()}")
            return None

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
            try:
                accounts = await client.get_game_accounts()
            except Exception as exc:
                await show_error_banner(page, message=str(exc))
                return None

            if not accounts:
                message = translator.translate(
                    LocaleStr(
                        key="no_game_accounts_error_message",
                        platform=EnumStr(params.platform or Platform.HOYOLAB),
                    ),
                    locale,
                )
                await show_error_banner(page, message=message)
                return None

            view = pages.FinishPage(
                params=params,
                translator=self._translator,
                locale=locale,
                accounts=accounts,
                cookies=cookies,
                device_id=device_id,
                device_fp=device_fp,
            )

        return view

    async def _handle_login_routes(
        self, route: str, parsed_params: dict[str, str]
    ) -> ft.View | None:
        page = self._page

        if route == "/geetest":
            query: str | None = await page.client_storage.get_async(
                f"hb.{parsed_params['user_id']}.params"
            )
            if query is None:
                return pages.ErrorPage(code=400, message="Cannot find params in client storage.")

            parsed_params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}

        try:
            params = Params(**parsed_params)  # pyright: ignore[reportArgumentType]
            locale = Locale(params.locale)
        except (ValidationError, ValueError):
            view = pages.ErrorPage(code=422, message="Invalid parameters")
        else:
            match route:
                case "/platforms":
                    await reset_storage(page, user_id=params.user_id)
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
                total_row = await self._get_gacha_log_row_num(params)
                gacha_logs = await self._get_gacha_logs(params)

                gacha_icons = await self._get_gacha_icons(gacha_logs)
                asyncio.create_task(page.client_storage.set_async("hb.gacha_icons", gacha_icons))

                game = await self._get_account_game(params.account_id)
                gacha_names = await self._get_gacha_names(
                    gachas=gacha_logs, locale=locale, game=game
                )
                asyncio.create_task(
                    page.client_storage.set_async(f"hb.{params.locale}.gacha_names", gacha_names)
                )

                if params.name_contains:
                    gacha_logs = [
                        g
                        for g in gacha_logs
                        if params.name_contains in gacha_names[g.item_id].lower()
                    ][(params.page - 1) * params.size : params.page * params.size]

                view = pages.GachaLogPage(
                    translator=self._translator,
                    locale=locale,
                    gacha_histories=gacha_logs,
                    gacha_icons=gacha_icons,
                    gacha_names=gacha_names,
                    game=game,
                    params=params,
                    max_page=(total_row + params.size - 1) // params.size,
                )
            case _:
                view = pages.ErrorPage(code=404, message="Not Found")

        return view

    @staticmethod
    async def _get_account_game(account_id: int) -> Game:
        conn = await asyncpg.connect(os.environ["DB_URL"])
        try:
            game = await conn.fetchval('SELECT game FROM "hoyoaccount" WHERE id = $1', account_id)
            return Game(game)
        finally:
            await conn.close()

    @staticmethod
    async def _get_gacha_log_row_num(params: GachaParams) -> int:
        conn = await asyncpg.connect(os.environ["DB_URL"])
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
    async def _get_gacha_logs(params: GachaParams) -> list[GachaHistory]:
        conn = await asyncpg.connect(os.environ["DB_URL"])
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
        cached_gacha_icons: dict[int, str] = (
            await self._page.client_storage.get_async("hb.gacha_icons") or {}
        )
        result: dict[int, str] = {}
        for gacha in gachas:
            if gacha.item_id in cached_gacha_icons:
                result[gacha.item_id] = cached_gacha_icons[gacha.item_id]
            else:
                result[gacha.item_id] = await get_gacha_icon(game=gacha.game, item_id=gacha.item_id)
                cached_gacha_icons[gacha.item_id] = result[gacha.item_id]

        asyncio.create_task(self._page.client_storage.set_async("gacha_icons", cached_gacha_icons))
        return result

    async def _get_json_file(self, filename: str) -> dict[str, str]:
        conn = await asyncpg.connect(os.environ["DB_URL"])
        try:
            json_string = await conn.fetchval(
                'SELECT data FROM "jsonfile" WHERE name = $1', filename
            )
            return orjson.loads(json_string)
        finally:
            await conn.close()

    async def _get_gacha_names(
        self, *, gachas: Sequence[GachaHistory], locale: Locale, game: Game
    ) -> dict[int, str]:
        cached_gacha_names: dict[int, str] = (
            await self._page.client_storage.get_async(f"hb.{locale}.{game.name}.gacha_names") or {}
        )

        result: dict[int, str] = {}
        item_ids = list({g.item_id for g in gachas})
        non_cached_item_ids: list[int] = []

        for item_id in item_ids:
            if item_id in cached_gacha_names:
                result[item_id] = cached_gacha_names[item_id]
            else:
                non_cached_item_ids.append(item_id)

        if game is Game.ZZZ:
            item_names = await self._get_json_file(
                f"zzz_item_names_{locale_to_zenless_data_lang(locale)}.json"
            )
            for item_id in item_ids:
                result[item_id] = item_names.get(str(item_id), str(item_id))
                cached_gacha_names[item_id] = result[item_id]
        else:
            async with aiohttp.ClientSession() as session:
                item_names = await item_id_to_name(
                    session,
                    item_ids=non_cached_item_ids,
                    game=game,
                    lang=locale_to_gpy_lang(locale),
                )
            for item_id in item_ids:
                index = item_ids.index(item_id)
                result[item_id] = item_names[index]
                cached_gacha_names[item_id] = item_names[index]

        asyncio.create_task(
            self._page.client_storage.set_async(
                f"hb.{locale}.{game.name}.gacha_names", cached_gacha_names
            )
        )

        return result

    @property
    def login_app_bar(self) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Text("Hoyo Buddy Login System"),
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                ft.IconButton(ft.icons.QUESTION_MARK, url="https://discord.com/invite/ryfamUykRw")
            ],
        )

    @property
    def gacha_app_bar(self) -> ft.AppBar:
        return ft.AppBar(
            title=ft.Text("Hoyo Buddy GachaLog System"),
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                ft.IconButton(ft.icons.QUESTION_MARK, url="https://discord.com/invite/ryfamUykRw")
            ],
        )
