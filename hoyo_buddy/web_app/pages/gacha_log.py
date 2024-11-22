from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import aiohttp
import flet as ft

from hoyo_buddy.constants import (
    BANNER_TYPE_NAMES,
    locale_to_gpy_lang,
    locale_to_starrail_data_lang,
    locale_to_zenless_data_lang,
)
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr, translator
from hoyo_buddy.utils import item_id_to_name
from hoyo_buddy.web_app.utils import fetch_json_file, show_error_banner

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

    from hoyo_buddy.db.models import GachaHistory
    from hoyo_buddy.web_app.schema import GachaParams

__all__ = ("GachaLogPage",)


class GachaLogPage(ft.View):
    def __init__(
        self,
        *,
        gacha_histories: Sequence[GachaHistory],
        gacha_icons: dict[int, str],
        params: GachaParams,
        game: Game,
        locale: Locale,
        max_page: int,
    ) -> None:
        self.game = game
        self.gachas = gacha_histories
        self.gacha_icons = gacha_icons
        self.params = params
        self.locale = locale
        self.max_page = max_page

        super().__init__(
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.TextField(
                                        label=translator.translate(
                                            LocaleStr(key="gacha_view_search_field_label"), locale
                                        ),
                                        prefix_icon=ft.icons.SEARCH,
                                        on_submit=self.on_search_bar_submit,
                                        value=params.name_contains,
                                    ),
                                    ft.OutlinedButton(
                                        text=translator.translate(
                                            LocaleStr(key="gacha_view_filter_button_label"), locale
                                        ),
                                        icon=ft.icons.FILTER_ALT,
                                        on_click=self.filter_button_on_click,
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.ARROW_BACK_IOS,
                                        on_click=self.previous_page_on_click,
                                        disabled=params.page == 1,
                                    ),
                                    ft.TextField(
                                        label=translator.translate(
                                            LocaleStr(key="gacha_view_page_field_label"), locale
                                        ),
                                        value=str(params.page),
                                        keyboard_type=ft.KeyboardType.NUMBER,
                                        on_submit=self.page_field_on_submit,
                                        width=80,
                                    ),
                                    ft.IconButton(
                                        icon=ft.icons.ARROW_FORWARD_IOS,
                                        on_click=self.next_page_on_click,
                                        disabled=params.page == max_page,
                                    ),
                                ],
                                wrap=True,
                            ),
                            ft.GridView(
                                self.gacha_log_controls,
                                expand=1,
                                runs_count=5,
                                max_extent=100,
                                child_aspect_ratio=1.0,
                                spacing=16,
                                run_spacing=16,
                            ),
                        ]
                    ),
                    minimum_padding=8,
                )
            ]
        )

    @property
    def gacha_log_controls(self) -> list[ft.Container]:
        rarity_colors: dict[int, str] = {3: "#3e4857", 4: "#4d3e66", 5: "#915537"}
        paddings: dict[Game, int] = {Game.GENSHIN: 0, Game.ZZZ: 8, Game.STARRAIL: 0}
        result: list[ft.Container] = []

        for gacha in self.gachas:
            stack_controls = [
                ft.Container(
                    ft.Image(src=self.gacha_icons[gacha.item_id], border_radius=8),
                    padding=ft.padding.all(paddings[self.game]),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    ft.Text(f"#{gacha.num}"),
                                    border_radius=5,
                                    bgcolor=ft.colors.SURFACE_VARIANT,
                                    padding=ft.padding.symmetric(vertical=2, horizontal=4),
                                )
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ]
            if gacha.rarity != 3:
                stack_controls.append(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        ft.Text(str(gacha.num_since_last)),
                                        border_radius=5,
                                        bgcolor=ft.colors.SURFACE_VARIANT,
                                        padding=ft.padding.symmetric(vertical=2, horizontal=4),
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.START,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    )
                )

            result.append(
                ft.Container(
                    ft.Stack(stack_controls),
                    bgcolor=rarity_colors[gacha.rarity],
                    border_radius=8,
                    on_click=self.container_on_click,
                    data=gacha.id,
                )
            )

        return result

    @staticmethod
    async def _get_gacha_name(
        page: ft.Page, gacha: GachaHistory, locale: Locale, game: Game
    ) -> str:
        cached_gacha_names: dict[int, str] = (
            await page.client_storage.get_async(f"hb.{locale}.{game.name}.gacha_names") or {}
        )
        if gacha.item_id in cached_gacha_names:
            return cached_gacha_names[gacha.item_id]

        if game is Game.ZZZ:
            item_names = await fetch_json_file(
                f"zzz_item_names_{locale_to_zenless_data_lang(locale)}.json"
            )
            item_name = item_names.get(str(gacha.item_id))
        elif game is Game.STARRAIL:
            item_names = await fetch_json_file(
                f"hsr_item_names_{locale_to_starrail_data_lang(locale)}.json"
            )
            item_name = item_names.get(str(gacha.item_id))
        else:
            async with aiohttp.ClientSession() as session:
                item_name = await item_id_to_name(
                    session, item_ids=gacha.item_id, lang=locale_to_gpy_lang(locale)
                )

        if item_name is not None:
            cached_gacha_names[gacha.item_id] = item_name
            asyncio.create_task(
                page.client_storage.set_async(
                    f"hb.{locale}.{game.name}.gacha_names", cached_gacha_names
                )
            )

        return item_name or "???"

    async def container_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        gacha = next(g for g in self.gachas if g.id == e.control.data)

        await page.show_dialog_async(
            GachaLogDialog(
                gacha=gacha,
                gacha_name=await self._get_gacha_name(page, gacha, self.locale, self.game),
                locale=self.locale,
            )
        )

    async def filter_button_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.show_dialog_async(
            FilterDialog(params=self.params, game=self.game, locale=self.locale)
        )

    async def on_search_bar_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.name_contains = e.control.value.lower()
        self.params.page = 1
        await page.go_async(f"/gacha_log?{self.params.to_query_string()}")

    async def next_page_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.page += 1
        await page.go_async(f"/gacha_log?{self.params.to_query_string()}")

    async def previous_page_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.page -= 1
        await page.go_async(f"/gacha_log?{self.params.to_query_string()}")

    async def page_field_on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page_num = int(e.control.value)
        if page_num < 1 or page_num > self.max_page:
            await show_error_banner(page, message="Invalid page number")
            return

        self.params.page = page_num
        await page.go_async(f"/gacha_log?{self.params.to_query_string()}")


class GachaLogDialog(ft.AlertDialog):
    def __init__(self, *, gacha: GachaHistory, gacha_name: str, locale: Locale) -> None:
        gacha_time = gacha.time.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        time_string = gacha_time.strftime("%Y-%m-%d %H:%M:%S") + " UTC+8"

        text = translator.translate(
            LocaleStr(
                key="gacha_view_gacha_detail", time=time_string, name=gacha_name, id=gacha.wish_id
            ),
            locale,
        )

        if gacha.num_since_last != 0:
            num_since_last = translator.translate(
                LocaleStr(
                    key="gacha_view_num_since_last", pull=gacha.num_since_last, rarity=gacha.rarity
                ),
                locale,
            )
            text += f"\n{num_since_last}"

        super().__init__(
            content=ft.Text(text),
            title=ft.Text(
                translator.translate(LocaleStr(key="gacha_view_gacha_detail_title"), locale)
            ),
            actions=[
                ft.TextButton(
                    text=translator.translate(LocaleStr(key="close_button_label"), locale),
                    on_click=self.close_dialog,
                )
            ],
        )

    async def close_dialog(self, e: ft.ControlEvent) -> None:
        await e.page.close_dialog_async()


class FilterDialog(ft.AlertDialog):
    def __init__(self, *, params: GachaParams, game: Game, locale: Locale) -> None:
        self.locale = locale
        self.params = params
        self.game = game

        super().__init__(
            title=ft.Text(
                translator.translate(LocaleStr(key="gacha_view_filter_dialog_title"), locale)
            ),
            actions=[
                ft.TextButton(
                    text=translator.translate(LocaleStr(key="cancel_button_label"), locale),
                    on_click=self.on_dialog_cancel,
                ),
                ft.TextButton(
                    text=translator.translate(
                        LocaleStr(key="set_cur_temp_as_default.done"), locale
                    ),
                    on_click=self.on_dialog_close,
                ),
            ],
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Checkbox(
                                label=f"{rarity} ★",
                                value=rarity in params.rarities,
                                data=rarity,
                                on_change=self.on_rarity_checkbox_change,
                            )
                            for rarity in (3, 4, 5)
                        ]
                    ),
                    ft.Dropdown(
                        options=[
                            ft.dropdown.Option(
                                text=translator.translate(
                                    LocaleStr(key=BANNER_TYPE_NAMES[game][banner_type]), locale
                                ),
                                data=str(banner_type),
                            )
                            for banner_type in BANNER_TYPE_NAMES[game]
                        ],
                        value=translator.translate(
                            LocaleStr(key=BANNER_TYPE_NAMES[game][params.banner_type]), locale
                        ),
                        on_change=self.on_banner_type_dropdown_change,
                    ),
                    ft.TextField(
                        label=translator.translate(
                            LocaleStr(key="gacha_view_filter_size_field_label"), locale
                        ),
                        value=str(params.size),
                        on_change=self.on_size_text_field_change,
                    ),
                ],
                tight=True,
            ),
        )

    async def on_banner_type_dropdown_change(self, e: ft.ControlEvent) -> None:
        banner_type_name_to_value = {
            translator.translate(LocaleStr(key=v), self.locale): k
            for k, v in BANNER_TYPE_NAMES[self.game].items()
        }
        self.params.banner_type = banner_type_name_to_value[e.control.value]

    async def on_rarity_checkbox_change(self, e: ft.ControlEvent) -> None:
        rarity = e.control.data
        if rarity in self.params.rarities:
            self.params.rarities.remove(rarity)
        else:
            self.params.rarities.append(rarity)

    async def on_size_text_field_change(self, e: ft.ControlEvent) -> None:
        size = int(e.control.value)
        self.params.size = min(max(size, 1), 500)

    async def on_dialog_close(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.close_dialog_async()
        self.params.page = 1
        await page.go_async(f"/gacha_log?{self.params.to_query_string()}")

    async def on_dialog_cancel(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.close_dialog_async()
