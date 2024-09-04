from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import asyncpg
import flet as ft
import genshin

from ...constants import GPY_GAME_TO_HB_GAME
from ...enums import Platform
from ...l10n import EnumStr, LocaleStr, Translator
from ...utils import get_discord_protocol_url, get_discord_url
from ..utils import show_error_snack_bar

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale
    from genshin.models import GenshinAccount

    from ..schema import Params

__all__ = ("FinishPage",)


class FinishPage(ft.View):
    def __init__(
        self,
        *,
        params: Params,
        translator: Translator,
        locale: Locale,
        accounts: Sequence[GenshinAccount],
        cookies: str,
        device_id: str | None,
        device_fp: str | None,
    ) -> None:
        self._params = params
        self._translator = translator
        self._locale = locale
        self._accounts = accounts
        self._selected_accounts: list[GenshinAccount] = []

        super().__init__(
            route="/finish",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(
                                translator.translate(
                                    LocaleStr(key="select_account.embed.title"), locale
                                ),
                                size=24,
                            ),
                            ft.Text(
                                translator.translate(
                                    LocaleStr(key="select_account.embed.description"), locale
                                )
                            ),
                        ]
                    )
                )
            ],
        )
        for account in accounts:
            hb_game = GPY_GAME_TO_HB_GAME[account.game]
            game_name = translator.translate(EnumStr(hb_game), locale)
            self.controls.append(
                ft.Checkbox(
                    label=f"[{game_name}] {account.nickname} | UID: {account.uid} | {account.server_name} | Lv.{account.level}",
                    data=f"{account.game.value}_{account.uid}",
                    on_change=self.on_checkbox_click,
                )
            )
        self.controls.append(
            SubmitButton(
                params=params,
                accounts=self._selected_accounts,
                cookies=cookies,
                translator=translator,
                locale=locale,
                device_id=device_id,
                device_fp=device_fp,
            )
        )

    async def on_checkbox_click(self, e: ft.ControlEvent) -> None:
        control: ft.Checkbox = e.control
        account = next(
            (acc for acc in self._accounts if f"{acc.game.value}_{acc.uid}" == control.data), None
        )
        if account is None:
            await show_error_snack_bar(e.page, message="Could not find account")
            return

        if control.value is True:
            self._selected_accounts.append(account)
        else:
            self._selected_accounts.remove(account)


class SubmitButton(ft.FilledButton):
    def __init__(
        self,
        *,
        params: Params,
        accounts: Sequence[GenshinAccount],
        cookies: str,
        device_id: str | None,
        device_fp: str | None,
        translator: Translator,
        locale: Locale,
    ) -> None:
        self._params = params
        self._accounts = accounts
        self._cookies = cookies
        self._device_id = device_id
        self._device_fp = device_fp
        self._translator = translator
        self._locale = locale
        super().__init__(
            translator.translate(LocaleStr(key="submit_button_label"), locale),
            on_click=self.add_accounts_to_db,
        )

    async def add_accounts_to_db(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        user_id = self._params.user_id
        region = (
            genshin.Region.CHINESE
            if self._params.platform is Platform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )

        conn = await asyncpg.connect(os.environ["DB_URL"])
        try:
            for account in self._accounts:
                await conn.execute(
                    "INSERT INTO hoyoaccount (uid, username, game, cookies, user_id, server, device_id, device_fp, region, redeemed_codes) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) ON CONFLICT (uid, game, user_id) DO UPDATE SET cookies = $4, username = $2, device_id = $7, device_fp = $8, region = $9",
                    account.uid,
                    account.nickname,
                    GPY_GAME_TO_HB_GAME[account.game],
                    self._cookies,
                    user_id,
                    account.server_name,
                    self._device_id,
                    self._device_fp,
                    region,
                    "[]",
                )
                account_id = await conn.fetchval(
                    "SELECT id FROM hoyoaccount WHERE uid = $1 AND game = $2 AND user_id = $3",
                    account.uid,
                    GPY_GAME_TO_HB_GAME[account.game],
                    user_id,
                )
                await conn.execute(
                    "INSERT INTO accountnotifsettings (account_id) VALUES ($1) ON CONFLICT DO NOTHING",
                    account_id,
                )
        finally:
            await conn.close()

        # Delete cookies and device info from client storage
        await page.client_storage.remove_async(f"hb.{user_id}.cookies")
        if await page.client_storage.contains_key_async(f"hb.{user_id}.device_id"):
            await page.client_storage.remove_async(f"hb.{user_id}.device_id")
        if await page.client_storage.contains_key_async(f"hb.{user_id}.device_fp"):
            await page.client_storage.remove_async(f"hb.{user_id}.device_fp")

        await page.show_snack_bar_async(
            ft.SnackBar(
                ft.Text(
                    self._translator.translate(
                        LocaleStr(key="accounts_added_snackbar_message"), self._locale
                    ),
                    color=ft.colors.ON_PRIMARY_CONTAINER,
                ),
                bgcolor=ft.colors.PRIMARY_CONTAINER,
            )
        )
        await asyncio.sleep(3)

        # Redirect to Discord
        url = get_discord_protocol_url(
            channel_id=str(self._params.channel_id), guild_id=str(self._params.guild_id)
        )
        if await page.can_launch_url_async(url):
            await page.launch_url_async(url)
        else:
            url = get_discord_url(
                channel_id=str(self._params.channel_id), guild_id=str(self._params.guild_id)
            )
            await page.launch_url_async(url)
