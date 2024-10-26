from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

import asyncpg
import flet as ft
import genshin
import orjson

from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient

from ..constants import GEETEST_SERVERS
from ..l10n import LocaleStr, Translator
from ..models import GeetestLoginPayload
from .utils import decrypt_string, encrypt_string, show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from discord import Locale
    from genshin.models import ActionTicket, SessionMMT

    from .schema import Params


async def handle_session_mmt(
    result: SessionMMT,
    *,
    page: ft.Page,
    params: Params,
    translator: Translator | None = None,
    locale: Locale | None = None,
    mmt_type: Literal["on_login", "on_email_send", "on_otp_send"],
    email: str | None = None,
    password: str | None = None,
    mobile: str | None = None,
) -> None:
    await page.client_storage.set_async(f"hb.{params.user_id}.gt_type", mmt_type)

    if email is not None:
        await page.client_storage.set_async(f"hb.{params.user_id}.email", encrypt_string(email))
    if password is not None:
        await page.client_storage.set_async(f"hb.{params.user_id}.password", encrypt_string(password))
    if mobile is not None:
        await page.client_storage.set_async(f"hb.{params.user_id}.mobile", encrypt_string(mobile))

    # Save mmt data to db
    conn = await asyncpg.connect(os.environ["DB_URL"])
    try:
        await conn.execute(
            'UPDATE "user" SET temp_data = $1 WHERE id = $2', orjson.dumps(result.model_dump()).decode(), params.user_id
        )
    finally:
        await conn.close()

    # Save current params
    await page.client_storage.set_async(f"hb.{params.user_id}.params", params.to_query_string())

    payload = GeetestLoginPayload(user_id=params.user_id, gt_version=3 if mmt_type != "on_otp_send" else 4)

    titles: dict[Literal["on_login", "on_email_send", "on_otp_send"], LocaleStr | str] = {
        "on_login": LocaleStr(key="geetest.embed.title"),
        "on_email_send": LocaleStr(key="email-geetest.embed.title"),
        "on_otp_send": "需要完成 CAPTCHA 验证才能寄送验证码",
    }
    title = titles[mmt_type]

    if isinstance(title, LocaleStr):
        assert translator is not None
        assert locale is not None

        title = translator.translate(title, locale)
        content = translator.translate(LocaleStr(key="captcha.embed.description"), locale)
        button_label = translator.translate(LocaleStr(key="complete_captcha_button_label"), locale)
    else:
        # Miyoushe
        content = "点击下方的按钮前往完成 CAPTCHA"
        button_label = "前往"

    await page.show_dialog_async(
        ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(content),
            actions=[
                ft.TextButton(
                    button_label,
                    url=f"{GEETEST_SERVERS[os.environ['ENV']]}/captcha?{payload.to_query_string()}",
                    url_target=ft.UrlTarget.SELF,
                )
            ],
            modal=True,
        )
    )


class EmailVerifyDialog(ft.AlertDialog):
    def __init__(
        self, ticket: ActionTicket, *, translator: Translator, locale: Locale, user_id: int, params: Params
    ) -> None:
        field_ref = ft.Ref[ft.TextField]()
        super().__init__(
            title=ft.Text(translator.translate(LocaleStr(key="email_verification_dialog_title"), locale)),
            content=ft.Column(
                [
                    ft.Text(translator.translate(LocaleStr(key="email_verification_dialog_content"), locale)),
                    ft.TextField(
                        label=translator.translate(LocaleStr(key="email_verification_field_label"), locale),
                        prefix_icon=ft.icons.NUMBERS,
                        max_length=6,
                        ref=field_ref,
                    ),
                    EmailVerifyCodeButton(
                        translator=translator,
                        locale=locale,
                        ticket=ticket,
                        field_ref=field_ref,
                        user_id=user_id,
                        params=params,
                    ),
                ],
                tight=True,
            ),
            modal=True,
        )


class EmailVerifyCodeButton(ft.FilledButton):
    def __init__(
        self,
        *,
        translator: Translator,
        locale: Locale,
        ticket: ActionTicket,
        field_ref: ft.Ref[ft.TextField],
        user_id: int,
        params: Params,
    ) -> None:
        super().__init__(translator.translate(LocaleStr(key="email_verification_dialog_action"), locale))
        self._translator = translator
        self._locale = locale
        self._ticket = ticket
        self._field_ref = field_ref
        self._user_id = user_id
        self._params = params

    async def verify_code(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        field = self._field_ref.current
        if not field.value:
            field.error_text = self._translator.translate(LocaleStr(key="required_field_error_message"), self._locale)
            await field.update_async()
            return

        await page.close_dialog_async()
        await show_loading_snack_bar(page, translator=self._translator, locale=self._locale)

        client = ProxyGenshinClient()
        try:
            await client._verify_email(field.value, self._ticket)
        except Exception as exc:
            await show_error_banner(page, message=str(exc))
            return

        encrypted_email = await page.client_storage.get_async(f"hb.{self._user_id}.email")
        encrypted_password = await page.client_storage.get_async(f"hb.{self._user_id}.password")
        if not isinstance(encrypted_email, str) or not isinstance(encrypted_password, str):
            await show_error_banner(page, message="Cannot find email or password in client storage.")
            return

        email = decrypt_string(encrypted_email)
        password = decrypt_string(encrypted_password)

        try:
            result = await client._app_login(email, password, ticket=self._ticket)
        except Exception as exc:
            await show_error_banner(page, message=str(exc))
            return

        cookies = result.to_str()
        encrypted_cookies = encrypt_string(cookies)
        await page.client_storage.set_async(f"hb.{self._user_id}.cookies", encrypted_cookies)
        await page.go_async(f"/finish?{self._params.to_query_string()}")


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
        EmailVerifyDialog(ticket=result, translator=translator, locale=locale, user_id=params.user_id, params=params)
    )


class MobileVerifyDialog(ft.AlertDialog):
    def __init__(self, *, mobile: str, user_id: int, params: Params) -> None:
        field_ref = ft.Ref[ft.TextField]()
        super().__init__(
            title=ft.Text("请输入验证码"),
            content=ft.Column(
                [
                    ft.Text("我们已经发送了验证码到您的手机, 请输入验证码以继续"),
                    ft.TextField(
                        label="验证码", prefix_icon=ft.icons.NUMBERS, max_length=6, ref=field_ref, hint_text="123456"
                    ),
                ],
                tight=True,
            ),
            actions=[MobileVerifyCodeButton(mobile=mobile, field_ref=field_ref, user_id=user_id, params=params)],
            modal=True,
        )


class MobileVerifyCodeButton(ft.TextButton):
    def __init__(self, *, mobile: str, field_ref: ft.Ref[ft.TextField], user_id: int, params: Params) -> None:
        super().__init__("验证", on_click=self.verify_code)
        self._mobile = mobile
        self._field_ref = field_ref
        self._user_id = user_id
        self._params = params

    async def verify_code(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        field = self._field_ref.current
        if not field.value:
            field.error_text = "此栏位为必填栏位"
            await field.update_async()
            return
        if len(field.value) != 6:
            field.error_text = "验证码长度必须为 6 位"
            await field.update_async()
            return

        await page.close_dialog_async()

        client = ProxyGenshinClient(region=genshin.Region.CHINESE)
        try:
            result = await client._login_with_mobile_otp(self._mobile, field.value)
        except Exception as exc:
            await show_error_banner(page, message=str(exc))
        else:
            cookies = result.to_str()
            encrypted_cookies = encrypt_string(cookies)
            await page.client_storage.set_async(f"hb.{self._user_id}.cookies", encrypted_cookies)
            await page.go_async(f"/finish?{self._params.to_query_string()}")


async def handle_mobile_otp(*, mobile: str, page: ft.Page, params: Params) -> None:
    await page.show_dialog_async(MobileVerifyDialog(mobile=mobile, user_id=params.user_id, params=params))
