from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import flet as ft
import genshin
from loguru import logger

from hoyo_buddy.constants import get_docs_url, locale_to_gpy_lang
from hoyo_buddy.enums import Platform
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.l10n import LocaleStr, translator

from ..login_handler import handle_action_ticket, handle_session_mmt
from ..utils import encrypt_string, show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale

    from ..schema import Params

__all__ = ("EmailPasswordPage",)

type LoginResult = (
    genshin.models.AppLoginResult
    | genshin.models.CNWebLoginResult
    | genshin.models.ActionTicket
    | genshin.models.SessionMMT
)


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
                                translator.translate(
                                    LocaleStr(key="email_password_button_label"), locale
                                ),
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
        control.update()

    async def on_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = (
            translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
            if not control.value
            else None
        )
        control.update()

    async def validate_form_fields(self) -> tuple[str, str]:
        """Validate email and password fields, showing errors if empty."""
        email = self._email_ref.current.value
        password = self._password_ref.current.value

        if not email:
            self._show_field_error(self._email_ref.current)
        if not password:
            self._show_field_error(self._password_ref.current)

        return email.strip() if email else "", password or ""

    def _show_field_error(self, field: ft.TextField) -> None:
        """Show required field error on the given field."""
        field.error_text = translator.translate(
            LocaleStr(key="required_field_error_message"), self._locale
        )
        field.update()

    async def perform_login(self, email: str, password: str, page: ft.Page) -> LoginResult | None:
        """Attempt to login with the given credentials."""
        client = self._create_genshin_client()

        try:
            if self._params.platform is Platform.HOYOLAB:
                return await client._app_login(email, password)
            return await client._cn_web_login(email, password)
        except genshin.GenshinException as exc:
            self._handle_genshin_exception(exc, page)
        except Exception as exc:
            logger.exception(f"[{self._params.user_id}] Email and password login error: {exc}")
            show_error_banner(page, message=str(exc))

        return None

    def _create_genshin_client(self) -> ProxyGenshinClient:
        """Create and configure a new Genshin client."""
        region = (
            genshin.Region.CHINESE
            if self._params.platform is Platform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )
        return ProxyGenshinClient(region=region, lang=locale_to_gpy_lang(self._locale))

    def _handle_genshin_exception(self, exc: genshin.GenshinException, page: ft.Page) -> None:
        """Handle GenshinException with appropriate error messages."""
        logger.debug(f"[{self._params.user_id}] Email and password login error: {exc}")

        if exc.retcode == -3006:  # Rate limited
            message = LocaleStr(key="too_many_requests_error_banner_msg").translate(self._locale)
            url = get_docs_url(
                "FAQ#too-many-requests-error-when-trying-to-add-accounts-using-email--password-method",
                locale=self._locale,
            )
        else:
            message = str(exc)
            url = None

        show_error_banner(page, message=message, url=url)

    async def handle_login_result(
        self, result: LoginResult, email: str, password: str, page: ft.Page
    ) -> None:
        """Process the login result and handle different response types."""
        if isinstance(result, genshin.models.SessionMMT):
            await self._handle_session_mmt(result, email, password, "on_login", page)
        elif isinstance(result, genshin.models.ActionTicket):
            await self._handle_action_ticket(result, email, password, page)
        else:  # Successful login with cookies
            await self._handle_successful_login(result, page)

    async def _handle_session_mmt(
        self,
        result: genshin.models.SessionMMT,
        email: str,
        password: str,
        mmt_type: Literal["on_login", "on_email_send"],
        page: ft.Page,
    ) -> None:
        """Handle SessionMMT response type."""
        logger.debug(f"[{self._params.user_id}] Got SessionMMT")
        await handle_session_mmt(
            result,
            email=email,
            password=password,
            page=page,
            params=self._params,
            locale=self._locale,
            mmt_type=mmt_type,
        )

    async def _handle_action_ticket(
        self, result: genshin.models.ActionTicket, email: str, password: str, page: ft.Page
    ) -> None:
        """Handle ActionTicket response type."""
        logger.debug(f"[{self._params.user_id}] Got ActionTicket")
        client = self._create_genshin_client()
        email_result = await client._send_verification_email(result)

        if isinstance(email_result, genshin.models.SessionMMT):
            await self._handle_session_mmt(email_result, email, password, "on_email_send", page)
        else:
            await handle_action_ticket(
                result,
                email=email,
                password=password,
                page=page,
                params=self._params,
                locale=self._locale,
            )

    async def _handle_successful_login(
        self, result: genshin.models.AppLoginResult | genshin.models.CNWebLoginResult, page: ft.Page
    ) -> None:
        """Handle successful login with cookies."""
        logger.debug(f"[{self._params.user_id}] Email and password login success")
        cookies = result.to_str()
        logger.debug(f"[{self._params.user_id}] Got cookies: {cookies}")
        encrypted_cookies = encrypt_string(cookies)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.cookies", encrypted_cookies)
        page.go(f"/finish?{self._params.to_query_string()}")

    async def on_submit(self, e: ft.ControlEvent) -> None:
        """Handle form submission with validation and login flow."""
        page = e.page

        if self._params.platform is None:
            show_error_banner(page, message="Invalid platform")
            return

        email, password = await self.validate_form_fields()
        if not email or not password:
            return

        show_loading_snack_bar(page, locale=self._locale)
        logger.debug(f"[{self._params.user_id}] Email and password login session started")

        result = await self.perform_login(email, password, page)
        if result is not None:
            await self.handle_login_result(result, email, password, page)

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
