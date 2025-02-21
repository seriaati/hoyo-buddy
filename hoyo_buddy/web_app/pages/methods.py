from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft

from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("MethodsPage",)


class MethodsPage(ft.View):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params

        self._locale = locale
        super().__init__(
            route="/methods",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(
                                translator.translate(
                                    LocaleStr(key="add_hoyolab_acc.embed.title"), locale
                                ),
                                size=24,
                            ),
                            self.get_description(locale),
                            ft.Container(
                                ft.Row(self.method_buttons, spacing=20, wrap=True),
                                margin=ft.margin.only(top=16),
                            ),
                        ]
                    )
                )
            ],
        )

    def get_description(self, locale: Locale) -> ft.Markdown | ft.Text:
        if self._params.platform is Platform.HOYOLAB:
            return ft.Markdown(
                translator.translate(LocaleStr(key="add_hoyolab_acc.embed.description"), locale),
                auto_follow_links=True,
                auto_follow_links_target=ft.UrlTarget.BLANK.value,
            )
        return ft.Text(
            "1. 通过改装过的米游社应用程序: 只有安卓裝置可使用\n2. 通过扫描二维码\n3. 通过手机号: 只有中国大陆手机号可使用\n4. 通过邮箱密码\n5. 通过开发者工具"
        )

    @property
    def method_buttons(self) -> list[MethodButton]:
        params, locale = self._params, self._locale

        if params.platform is Platform.HOYOLAB:
            return [
                MethodButton(
                    params=params,
                    label=translator.translate(
                        LocaleStr(key="email_password_button_label"), locale
                    ),
                    to_page="email_password",
                ),
                MethodButton(
                    params=params,
                    label=translator.translate(LocaleStr(key="devtools_button_label"), locale),
                    to_page="dev_tools",
                ),
            ]
        return [
            # MethodButton(params=params, label="通过改装过的米游社应用程序", to_page="mod_app"),
            MethodButton(params=params, label="通过扫描二维码", to_page="qrcode"),
            MethodButton(params=params, label="通过手机号", to_page="mobile"),
            MethodButton(params=params, label="通过邮箱密码", to_page="email_password"),
            MethodButton(params=params, label="通过开发者工具", to_page="dev_tools"),
        ]


class MethodButton(ft.FilledTonalButton):
    def __init__(self, *, params: Params, label: str, to_page: str, disabled: bool = False) -> None:
        self._params = params
        self._to_page = to_page
        super().__init__(text=label, on_click=self.on_btn_click, disabled=disabled)

    async def on_btn_click(self, e: ft.ControlEvent) -> Any:
        page: ft.Page = e.page
        page.go(f"/{self._to_page}?{self._params.to_query_string()}")
