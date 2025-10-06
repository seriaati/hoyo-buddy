from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flet as ft

from hoyo_buddy.constants import BANNER_TYPE_NAMES
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr, translator
from hoyo_buddy.web_app.utils import get_gacha_names, show_error_banner

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db import GachaHistory
    from hoyo_buddy.enums import Locale
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
                                        prefix_icon=ft.Icons.SEARCH,
                                        on_submit=self.on_search_bar_submit,
                                        value=params.name_contains,
                                    ),
                                    ft.OutlinedButton(
                                        text=translator.translate(
                                            LocaleStr(key="gacha_view_filter_button_label"), locale
                                        ),
                                        icon=ft.Icons.FILTER_ALT,
                                        on_click=self.filter_button_on_click,
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.ARROW_BACK_IOS,
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
                                        icon=ft.Icons.ARROW_FORWARD_IOS,
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
                                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
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
                                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
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

    async def container_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        gacha = next((g for g in self.gachas if g.id == e.control.data), None)
        if gacha is None:
            show_error_banner(page, message=f"Could not find gacha with id {e.control.data}")
            return

        gacha_names = await get_gacha_names(
            page, gachas=[gacha], locale=self.locale, game=self.game
        )

        page.open(
            GachaLogDialog(gacha=gacha, gacha_name=gacha_names[gacha.item_id], locale=self.locale)
        )

    async def filter_button_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page.open(FilterDialog(params=self.params, game=self.game, locale=self.locale))

    async def on_search_bar_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.name_contains = e.control.value.lower()
        self.params.page = 1
        page.go(f"/gacha_log?{self.params.to_query_string()}")

    async def next_page_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.page += 1
        page.go(f"/gacha_log?{self.params.to_query_string()}")

    async def previous_page_on_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        self.params.page -= 1
        page.go(f"/gacha_log?{self.params.to_query_string()}")

    async def page_field_on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page_num = int(e.control.value)
        if page_num < 1 or page_num > self.max_page:
            show_error_banner(page, message="Invalid page number")
            return

        self.params.page = page_num
        page.go(f"/gacha_log?{self.params.to_query_string()}")


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
        e.page.close(self)


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
                            LocaleStr(key=BANNER_TYPE_NAMES[game].get(params.banner_type, "")),
                            locale,
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
        try:
            size = int(e.control.value)
        except ValueError:
            return
        self.params.size = min(max(size, 1), 500)

    async def on_dialog_close(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page.close(self)
        self.params.page = 1
        page.go(f"/gacha_log?{self.params.to_query_string()}")

    async def on_dialog_cancel(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page.close(self)
