from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ...l10n import LocaleStr
from ..utils import encrypt_string, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("DevModePage",)


class DevModePage(ft.View):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params

        self._locale = locale
        super().__init__(
            route="/dev",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text("Developer Mode", size=24),
                            ft.Text("This page is only for development purposes.", size=16),
                            ft.Container(CookiesForm(params=params, locale=locale), margin=ft.margin.only(top=16)),
                        ],
                        wrap=True,
                    )
                )
            ],
        )


class CookiesForm(ft.Column):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params
        self._locale = locale
        self._cookies_ref = ft.Ref[ft.TextField]()
        super().__init__(
            [CookiesTextField(locale=locale, ref=self._cookies_ref), self.submit_button], wrap=True, spacing=16
        )

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(
            text=LocaleStr(key="submit_button_label").translate(self._locale), on_click=self.on_submit
        )

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        cookies = self._cookies_ref.current

        if not cookies.value:
            self._cookies_ref.current.error_text = LocaleStr(key="required_field_error_message").translate(self._locale)
            await self._cookies_ref.current.update_async()
            return

        await show_loading_snack_bar(page, locale=self._locale)
        encrypted_cookies = encrypt_string(cookies.value)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.cookies", encrypted_cookies)
        await page.go_async(f"/finish?{self._params.to_query_string()}")


class CookiesTextField(ft.TextField):
    def __init__(self, *, locale: Locale, ref: ft.Ref) -> None:
        self._locale = locale
        super().__init__(
            label="cookies",
            keyboard_type=ft.KeyboardType.TEXT,
            multiline=True,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
            prefix_icon=ft.icons.COOKIE,
            ref=ref,
            hint_text="Paste your cookies here",
        )

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = (
            LocaleStr(key="required_field_error_message").translate(self._locale) if not control.value else None
        )
        await control.update_async()

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()
