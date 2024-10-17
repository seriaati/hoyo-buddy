from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from ...l10n import LocaleStr, Translator
from ..utils import encrypt_string, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("DevToolsPage",)


class DevToolsPage(ft.View):
    def __init__(self, *, params: Params, translator: Translator, locale: Locale) -> None:
        self._params = params
        self._translator = translator
        self._locale = locale
        super().__init__(
            route="/dev_tools",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(translator.translate(LocaleStr(key="instructions_title"), locale), size=24),
                            ft.Markdown(
                                translator.translate(LocaleStr(key="devtools_instructions_description"), locale),
                                auto_follow_links=True,
                                auto_follow_links_target=ft.UrlTarget.BLANK.value,
                            ),
                            ft.ElevatedButton(
                                translator.translate(LocaleStr(key="show_tutorial_button_label"), locale),
                                on_click=lambda e: e.page.open(ShowImageDialog(translator=translator, locale=locale)),
                            ),
                            ft.Container(
                                DevToolsCookieForm(params=params, translator=translator, locale=locale),
                                margin=ft.margin.only(top=16),
                            ),
                        ]
                    )
                )
            ],
        )


class ShowImageDialog(ft.AlertDialog):
    def __init__(self, *, translator: Translator, locale: Locale) -> None:
        super().__init__(
            content=ft.Image(src="/images/dev_tools_tutorial.gif", border_radius=8),
            actions=[
                ft.TextButton(
                    translator.translate(LocaleStr(key="close_button_label"), locale),
                    on_click=lambda e: e.page.close(self),
                )
            ],
        )


class DevToolsCookieForm(ft.Column):
    def __init__(self, *, params: Params, translator: Translator, locale: Locale) -> None:
        self._params = params
        self._translator = translator
        self._locale = locale
        self._ltuid_v2_ref = ft.Ref[CookieField]()
        self._account_id_v2_ref = ft.Ref[CookieField]()
        self._ltoken_v2_ref = ft.Ref[CookieField]()
        self._ltmid_v2_ref = ft.Ref[CookieField]()
        self._account_mid_v2_ref = ft.Ref[CookieField]()

        super().__init__(
            [
                CookieField(
                    label="ltuid_v2", hint_text="1234567", ref=self._ltuid_v2_ref, translator=translator, locale=locale
                ),
                CookieField(
                    label="account_id_v2",
                    hint_text="1234567",
                    ref=self._account_id_v2_ref,
                    translator=translator,
                    locale=locale,
                ),
                CookieField(
                    label="ltoken_v2",
                    hint_text="v2_ABCDe5678",
                    ref=self._ltoken_v2_ref,
                    translator=translator,
                    locale=locale,
                ),
                CookieField(
                    label="ltmid_v2", hint_text="1k922_hy", ref=self._ltmid_v2_ref, translator=translator, locale=locale
                ),
                CookieField(
                    label="account_mid_v2",
                    hint_text="1k922_hy",
                    ref=self._account_mid_v2_ref,
                    translator=translator,
                    locale=locale,
                ),
                ft.Container(self.submit_button, margin=ft.margin.only(top=16)),
            ],
            wrap=True,
            spacing=16,
        )

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        ltuid_v2 = self._ltuid_v2_ref.current
        account_id_v2 = self._account_id_v2_ref.current
        ltoken_v2 = self._ltoken_v2_ref.current
        ltmid_v2 = self._ltmid_v2_ref.current
        account_mid_v2 = self._account_mid_v2_ref.current
        refs = (ltuid_v2, account_id_v2, ltoken_v2, ltmid_v2, account_mid_v2)

        for ref in refs:
            if not ref.value:
                ref.error_text = self._translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
                await ref.update_async()

        if all(ref.value for ref in refs):
            await show_loading_snack_bar(page, translator=self._translator, locale=self._locale)
            cookies = f"ltuid_v2={ltuid_v2.value}; account_id_v2={account_id_v2.value}; ltoken_v2={ltoken_v2.value}; ltmid_v2={ltmid_v2.value}; account_mid_v2={account_mid_v2.value}"
            encrypted_cookies = encrypt_string(cookies)
            await page.client_storage.set_async(f"hb.{self._params.user_id}.cookies", encrypted_cookies)
            await page.go_async(f"/finish?{self._params.to_query_string()}")

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(
            text=self._translator.translate(LocaleStr(key="submit_button_label"), self._locale), on_click=self.on_submit
        )


class CookieField(ft.TextField):
    def __init__(self, *, label: str, hint_text: str, ref: ft.Ref, translator: Translator, locale: Locale) -> None:
        self._translator = translator
        self._locale = locale
        super().__init__(
            keyboard_type=ft.KeyboardType.TEXT,
            label=label,
            hint_text=hint_text,
            ref=ref,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
        )

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = (
            self._translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
            if not control.value
            else None
        )
        await control.update_async()
