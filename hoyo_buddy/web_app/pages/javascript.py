from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ...l10n import LocaleStr, Translator
from ..utils import encrypt_string, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("JavascriptPage",)


class JavascriptPage(ft.View):
    def __init__(self, *, params: Params, translator: Translator, locale: Locale) -> None:
        self._params = params
        self._translator = translator
        self._locale = locale
        self._code = "script:document.write(document.cookie)"
        super().__init__(
            route="/javascript",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(
                                translator.translate(LocaleStr(key="instructions_title"), locale),
                                size=24,
                            ),
                            ft.Markdown(
                                translator.translate(
                                    LocaleStr(key="javascript_instructions_description"), locale
                                ),
                                auto_follow_links=True,
                                auto_follow_links_target=ft.UrlTarget.BLANK.value,
                            ),
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.ElevatedButton(
                                            translator.translate(
                                                LocaleStr(key="show_tutorial_button_label"), locale
                                            ),
                                            on_click=lambda e: e.page.open(
                                                ShowImageDialog(
                                                    translator=translator, locale=locale
                                                )
                                            ),
                                        ),
                                        ft.FilledTonalButton(
                                            text=translator.translate(
                                                LocaleStr(key="copy_code_button_label"), locale
                                            ),
                                            on_click=self.on_button_click,
                                            icon=ft.icons.COPY,
                                        ),
                                        CookiesForm(
                                            params=params, translator=translator, locale=locale
                                        ),
                                    ],
                                    spacing=16,
                                ),
                                margin=ft.margin.only(top=16),
                            ),
                        ],
                        wrap=True,
                    )
                )
            ],
        )

    async def on_button_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.set_clipboard_async(self._code)
        await page.show_snack_bar_async(
            ft.SnackBar(
                ft.Text(
                    self._translator.translate(LocaleStr(key="copied_to_clipboard"), self._locale),
                    color=ft.colors.ON_PRIMARY_CONTAINER,
                ),
                bgcolor=ft.colors.PRIMARY_CONTAINER,
            )
        )


class CookiesForm(ft.Column):
    def __init__(self, *, params: Params, translator: Translator, locale: Locale) -> None:
        self._params = params
        self._translator = translator
        self._locale = locale
        self._cookies_ref = ft.Ref[ft.TextField]()
        super().__init__(
            [
                CookiesTextField(translator=translator, locale=locale, ref=self._cookies_ref),
                ft.Container(self.submit_button, margin=ft.margin.only(top=16)),
            ],
            wrap=True,
            spacing=16,
        )

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(
            text=self._translator.translate(LocaleStr(key="submit_button_label"), self._locale),
            on_click=self.on_submit,
        )

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        cookies = self._cookies_ref.current

        if not cookies.value:
            self._cookies_ref.current.error_text = self._translator.translate(
                LocaleStr(key="required_field_error_message"), self._locale
            )
            await self._cookies_ref.current.update_async()
            return

        await show_loading_snack_bar(page, translator=self._translator, locale=self._locale)
        encrypted_cookies = encrypt_string(cookies.value)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.cookies", encrypted_cookies)
        await page.go_async(f"/finish?{self._params.to_query_string()}")


class CookiesTextField(ft.TextField):
    def __init__(self, *, translator: Translator, locale: Locale, ref: ft.Ref) -> None:
        self._translator = translator
        self._locale = locale
        super().__init__(
            label="cookies",
            keyboard_type=ft.KeyboardType.TEXT,
            multiline=True,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
            prefix_icon=ft.icons.COOKIE,
            ref=ref,
            hint_text=self._translator.translate(
                LocaleStr(key="cookies_modal_placeholder"), self._locale
            ),
        )

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = (
            self._translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
            if not control.value
            else None
        )
        await control.update_async()

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()


class ShowImageDialog(ft.AlertDialog):
    def __init__(self, *, translator: Translator, locale: Locale) -> None:
        super().__init__(
            content=ft.Image(src="/images/js_tutorial.gif", border_radius=8),
            actions=[
                ft.TextButton(
                    translator.translate(LocaleStr(key="close_button_label"), locale),
                    on_click=lambda e: e.page.close(self),
                )
            ],
        )
