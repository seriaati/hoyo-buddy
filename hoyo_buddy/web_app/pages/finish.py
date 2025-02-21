from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import asyncpg
import flet as ft
import genshin

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME
from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import LocaleStr, translator
from hoyo_buddy.utils import get_discord_protocol_url, get_discord_url

from ..utils import reset_storage, show_error_banner

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
        locale: Locale,
        accounts: Sequence[GenshinAccount],
        cookies: str,
        device_id: str | None,
        device_fp: str | None,
    ) -> None:
        self._params = params

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
            # account.game can be a str if the game is not recognized
            if not isinstance(account.game, genshin.Game):  # pyright: ignore[reportUnnecessaryIsInstance]
                continue

            self.controls.append(
                ft.ListTile(
                    leading=ft.CircleAvatar(
                        foreground_image_src=f"/images/{account.game.value}.png"
                    ),
                    title=ft.Text(f"[{account.uid}] {account.nickname}"),
                    subtitle=ft.Text(f"{account.server_name}, Lv.{account.level}"),
                    trailing=ft.Checkbox(
                        on_change=self.on_checkbox_click, data=f"{account.game.value}_{account.uid}"
                    ),
                    toggle_inputs=True,
                )
            )
        self.controls.append(
            ft.Container(
                SubmitButton(
                    params=params,
                    accounts=self._selected_accounts,
                    cookies=cookies,
                    locale=locale,
                    device_id=device_id,
                    device_fp=device_fp,
                ),
                margin=ft.margin.only(top=16),
            )
        )

    async def on_checkbox_click(self, e: ft.ControlEvent) -> None:
        control: ft.Checkbox = e.control
        account = next(
            (
                acc
                for acc in self._accounts
                if isinstance(acc.game, genshin.Game)  # pyright: ignore[reportUnnecessaryIsInstance]
                and f"{acc.game.value}_{acc.uid}" == control.data
            ),
            None,
        )
        if account is None:
            show_error_banner(e.page, message="Could not find account")
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
        locale: Locale,
    ) -> None:
        self._params = params
        self._accounts = accounts
        self._cookies = cookies
        self._device_id = device_id
        self._device_fp = device_fp

        self._locale = locale
        super().__init__(
            translator.translate(LocaleStr(key="submit_button_label"), locale),
            on_click=self.add_accounts_to_db,
        )

    async def add_accounts_to_db(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        if not self._accounts:
            show_error_banner(page, message="Please select at least one account")
            return

        user_id = self._params.user_id
        region = (
            genshin.Region.CHINESE
            if self._params.platform is Platform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )

        conn = await asyncpg.connect(CONFIG.db_url)
        try:
            await conn.execute(
                'INSERT INTO "user" (id, temp_data) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING',
                user_id,
                "{}",
            )
            await conn.execute(
                'INSERT INTO "settings" (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING',
                user_id,
            )

            account_id = None

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

            if account_id is not None:
                await conn.execute(
                    'UPDATE "hoyoaccount" SET current = false WHERE user_id = $1', user_id
                )
                await conn.execute(
                    'UPDATE "hoyoaccount" SET current = true WHERE id = $1', account_id
                )
        finally:
            await conn.close()

        # Delete cookies and device info from client storage
        reset_storage(page, user_id=user_id)

        page.open(
            ft.SnackBar(
                ft.Row(
                    [
                        ft.ProgressRing(
                            width=16,
                            height=16,
                            stroke_width=2,
                            color=ft.colors.ON_SECONDARY_CONTAINER,
                        ),
                        ft.Text(
                            translator.translate(
                                LocaleStr(key="accounts_added_snackbar_message"), self._locale
                            ),
                            color=ft.colors.ON_PRIMARY_CONTAINER,
                        ),
                    ],
                    wrap=True,
                ),
                bgcolor=ft.colors.PRIMARY_CONTAINER,
            )
        )
        await asyncio.sleep(3)

        channel_id, guild_id = self._params.channel_id, self._params.guild_id
        if channel_id is None:
            show_error_banner(page, message="Unable to redirect to Discord, cannot find channel ID")
            return

        # Redirect to Discord
        url = get_discord_protocol_url(channel_id=channel_id, guild_id=guild_id)
        try:
            can_launch = page.can_launch_url(url)
        except TimeoutError:
            can_launch = False

        if can_launch:
            page.launch_url(url, web_window_name=ft.UrlTarget.SELF.value)
        else:
            url = get_discord_url(channel_id=channel_id, guild_id=guild_id)
            page.launch_url(url, web_window_name=ft.UrlTarget.SELF.value)
