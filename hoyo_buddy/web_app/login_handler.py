from __future__ import annotations

import os
from typing import TYPE_CHECKING

import asyncpg
import flet as ft
import genshin

from ..constants import GEETEST_SERVERS
from ..enums import GeetestNotifyType, Platform
from ..l10n import LocaleStr, Translator
from ..models import GeetestPayload
from .utils import decrypt_string, encrypt_string, show_error_snack_bar

if TYPE_CHECKING:
    from discord import Locale
    from genshin.models import ActionTicket, SessionMMT

    from .schema import Params


async def handle_session_mmt(
    result: SessionMMT,
    *,
    email: str,
    password: str,
    page: ft.Page,
    params: Params,
    translator: Translator,
    locale: Locale,
    on_email_send: bool,
) -> None:
    await page.client_storage.set_async(
        f"hb.{params.user_id}.gt_type", "on_email_send" if on_email_send else "on_login"
    )
    await page.client_storage.set_async(f"hb.{params.user_id}.email", encrypt_string(email))
    await page.client_storage.set_async(f"hb.{params.user_id}.password", encrypt_string(password))

    # Save mmt data to db
    conn = await asyncpg.connect(os.environ["DB_URL"])
    try:
        await conn.execute(
            "UPDATE user SET temp_data = $1 WHERE id = $2", result.dict(), params.user_id
        )
    finally:
        await conn.close()

    payload = GeetestPayload(
        user_id=params.user_id,
        gt_version=3 if params.platform is Platform.HOYOLAB else 4,
        gt_type=GeetestNotifyType.LOGIN,
    )
    await page.show_dialog_async(
        ft.AlertDialog(
            title=ft.Text(
                translator.translate(
                    LocaleStr(
                        key="email-geetest.embed.title" if on_email_send else "geetest.embed.title"
                    ),
                    locale,
                )
            ),
            content=ft.Text(
                translator.translate(LocaleStr(key="captcha.embed.description"), locale)
            ),
            actions=[
                ft.TextButton(
                    translator.translate(LocaleStr(key="complete_captcha_button_label"), locale),
                    url=f"{GEETEST_SERVERS[os.environ['ENV']]}/captcha?{payload.to_query_string()}",
                )
            ],
        )
    )


class EmailVerificationDialog(ft.AlertDialog):
    def __init__(
        self, ticket: ActionTicket, *, translator: Translator, locale: Locale, user_id: int
    ) -> None:
        field_ref = ft.Ref[ft.TextField]()
        super().__init__(
            title=ft.Text(
                translator.translate(LocaleStr(key="email_verification_dialog_title"), locale)
            ),
            content=ft.Column(
                [
                    ft.Text(
                        translator.translate(
                            LocaleStr(key="email_verification_dialog_content"), locale
                        )
                    ),
                    ft.TextField(
                        label=translator.translate(
                            LocaleStr(key="email_verification_field_label"), locale
                        ),
                        prefix_icon=ft.icons.NUMBERS,
                        max_length=6,
                        ref=field_ref,
                    ),
                    VerifyCodeButton(
                        translator=translator,
                        locale=locale,
                        ticket=ticket,
                        field_ref=field_ref,
                        user_id=user_id,
                    ),
                ],
                wrap=True,
            ),
        )


class VerifyCodeButton(ft.FilledButton):
    def __init__(
        self,
        *,
        translator: Translator,
        locale: Locale,
        ticket: ActionTicket,
        field_ref: ft.Ref[ft.TextField],
        user_id: int,
    ) -> None:
        super().__init__(
            translator.translate(LocaleStr(key="email_verification_dialog_action"), locale)
        )
        self._translator = translator
        self._locale = locale
        self._ticket = ticket
        self._field_ref = field_ref
        self._user_id = user_id

    async def verify_code(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        field = self._field_ref.current
        if not field.value:
            field.error_text = self._translator.translate(
                LocaleStr(key="required_field_error_message"), self._locale
            )
            await field.update_async()
            return

        client = genshin.Client()
        await client._verify_email(field.value, self._ticket)

        encrypted_email = await page.client_storage.get_async(f"hb.{self._user_id}.email")
        encrypted_password = await page.client_storage.get_async(f"hb.{self._user_id}.password")
        if not isinstance(encrypted_email, str) or not isinstance(encrypted_password, str):
            await show_error_snack_bar(
                page, message="Cannot find email or password in client storage."
            )
            return

        email = decrypt_string(encrypted_email)
        password = decrypt_string(encrypted_password)

        result = await client._app_login(email, password, ticket=self._ticket)
        cookies = result.to_str()
        encrypted_cookies = encrypt_string(cookies)
        await page.client_storage.set_async(f"hb.{self._user_id}.cookies", encrypted_cookies)


async def handle_action_ticket(
    result: ActionTicket,
    *,
    email: str,
    password: str,
    page: ft.Page,
    params: Params,
    translator: Translator,
    locale: Locale,
) -> None:
    await page.client_storage.set_async(f"hb.{params.user_id}.email", encrypt_string(email))
    await page.client_storage.set_async(f"hb.{params.user_id}.password", encrypt_string(password))
    await page.show_dialog_async(
        EmailVerificationDialog(
            ticket=result, translator=translator, locale=locale, user_id=params.user_id
        )
    )
