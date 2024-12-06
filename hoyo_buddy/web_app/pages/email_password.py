from __future__ import annotations

from typing import TYPE_CHECKING, Any

import flet as ft
import genshin
from loguru import logger

from hoyo_buddy.constants import locale_to_gpy_lang
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient

from ...enums import Platform
from ...l10n import LocaleStr, translator
from ..login_handler import handle_action_ticket, handle_session_mmt
from ..utils import encrypt_string, show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("EmailPasswordPage",)


class EmailPasswordPage(ft.View):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params

        self._locale = locale

        super().__init__(
            route="/email_password",
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
                                    LocaleStr(key="enter_email_password_instructions_description"),
                                    locale,
                                ),
                                auto_follow_links=True,
                                auto_follow_links_target=ft.UrlTarget.BLANK.value,
                            ),
                            ft.Container(
                                EmailPassWordForm(params=params, locale=locale),
                                margin=ft.margin.only(top=16),
                            ),
                        ]
                    )
                )
            ],
        )


class EmailPassWordForm(ft.Column):
    def __init__(self, *, params: Params, locale: Locale) -> None:
        self._params = params

        self._locale = locale
        self._email_ref = ft.Ref[ft.TextField]()
        self._password_ref = ft.Ref[ft.TextField]()

        super().__init__(
            [
                self.email,
                self.password,
                ft.Container(self.submit_button, margin=ft.margin.only(top=16)),
            ],
            wrap=True,
            spacing=16,
        )

    async def on_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()

    async def on_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = (
            translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
            if not control.value
            else None
        )
        await control.update_async()

    async def on_submit(self, e: ft.ControlEvent) -> Any:
        page: ft.Page = e.page

        email_field = self._email_ref.current
        password_field = self._password_ref.current
        email = email_field.value
        password = password_field.value

        if not email:
            self._email_ref.current.error_text = translator.translate(
                LocaleStr(key="required_field_error_message"), self._locale
            )
            await self._email_ref.current.update_async()

        if not password:
            self._password_ref.current.error_text = translator.translate(
                LocaleStr(key="required_field_error_message"), self._locale
            )
            await self._password_ref.current.update_async()

        if not email or not password:
            return

        if self._params.platform is None:
            await show_error_banner(page, message="Invalid platform")
            return

        await show_loading_snack_bar(page, locale=self._locale)

        logger.debug(f"[{self._params.user_id}] Email and password login session started")
        client = ProxyGenshinClient(
            region=genshin.Region.CHINESE
            if self._params.platform is Platform.MIYOUSHE
            else genshin.Region.OVERSEAS,
            lang=locale_to_gpy_lang(self._locale),
        )
        try:
            if self._params.platform is Platform.HOYOLAB:
                result = await client.os_app_login(email.strip(), password)
            else:
                result = await client._cn_web_login(email.strip(), password)
        except Exception as exc:
            logger.debug(f"[{self._params.user_id}] Email and password login error: {exc}")
            await show_error_banner(page, message=str(exc))
            return

        if isinstance(result, genshin.models.SessionMMT):
            logger.debug(f"[{self._params.user_id}] Got SessionMMT")
            await handle_session_mmt(
                result,
                email=email,
                password=password,
                page=page,
                params=self._params,
                locale=self._locale,
                mmt_type="on_login",
            )
        elif isinstance(result, genshin.models.ActionTicket):
            logger.debug(f"[{self._params.user_id}] Got ActionTicket")
            email_result = await client._send_verification_email(result)
            if isinstance(email_result, genshin.models.SessionMMT):
                logger.debug(f"[{self._params.user_id}] Got SessionMMT from sending email")
                await handle_session_mmt(
                    email_result,
                    email=email,
                    password=password,
                    page=page,
                    params=self._params,
                    locale=self._locale,
                    mmt_type="on_email_send",
                )
            else:
                logger.debug(f"[{self._params.user_id}] Handling ActionTicket")
                await handle_action_ticket(
                    result,
                    email=email,
                    password=password,
                    page=page,
                    params=self._params,
                    locale=self._locale,
                )
        else:
            logger.debug(f"[{self._params.user_id}] Email and password login success")
            cookies = result.to_str()
            logger.debug(f"[{self._params.user_id}] Got cookies: {cookies}")
            encrypted_cookies = encrypt_string(cookies)
            await page.client_storage.set_async(
                f"hb.{self._params.user_id}.cookies", encrypted_cookies
            )
            await page.go_async(f"/finish?{self._params.to_query_string()}")

    @property
    def email(self) -> ft.TextField:
        return ft.TextField(
            keyboard_type=ft.KeyboardType.EMAIL,
            label=translator.translate(
                LocaleStr(key="email_password_modal_email_input_label"), self._locale
            ),
            hint_text="a@gmail.com",
            ref=self._email_ref,
            on_blur=self.on_blur,
            on_focus=self.on_focus,
            prefix_icon=ft.icons.EMAIL,
        )

    @property
    def password(self) -> ft.TextField:
        return ft.TextField(
            keyboard_type=ft.KeyboardType.TEXT,
            label=translator.translate(
                LocaleStr(key="email_password_modal_password_input_label"), self._locale
            ),
            hint_text="a123456",
            password=True,
            can_reveal_password=True,
            ref=self._password_ref,
            on_blur=self.on_blur,
            on_focus=self.on_focus,
            prefix_icon=ft.icons.PASSWORD,
        )

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(
            text=translator.translate(LocaleStr(key="submit_button_label"), self._locale),
            on_click=self.on_submit,
        )
