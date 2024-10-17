from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft
import genshin

from hoyo_buddy.web_app.login_handler import handle_mobile_otp, handle_session_mmt
from hoyo_buddy.web_app.utils import show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from ..schema import Params

__all__ = ("MobilePage",)


class MobilePage(ft.View):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        super().__init__(
            route="/mod_app",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text("指引", size=24),
                            ft.Text("1.点击下方按钮输入手机号\n2.你将会收到短信验证码\n3.点击下方按钮填写验证码"),
                            ft.Container(MobileNumberForm(params=params), margin=ft.margin.only(top=16)),
                        ]
                    )
                )
            ],
        )


class MobileNumberForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._mobile_number_ref = ft.Ref[ft.TextField]()

        super().__init__([MobileNumberField(ref=self._mobile_number_ref), self.submit_button], wrap=True, spacing=16)

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        login_details = self._mobile_number_ref.current

        if not login_details.value:
            login_details.error_text = "此栏位为必填栏位"
            await login_details.update_async()
        else:
            await show_loading_snack_bar(page, message="正在发送验证码...")
            mobile = login_details.value
            client = genshin.Client(region=genshin.Region.CHINESE)

            try:
                result = await client._send_mobile_otp(mobile)
            except Exception as exc:
                await show_error_banner(page=page, message=str(exc))
                return

            if isinstance(result, genshin.models.SessionMMT):
                await handle_session_mmt(result, page=page, params=self._params, mmt_type="on_otp_send", mobile=mobile)
            else:
                await handle_mobile_otp(mobile=mobile, page=page, params=self._params)

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(text="提交", on_click=self.on_submit)


class MobileNumberField(ft.TextField):
    def __init__(self, *, ref: ft.Ref) -> None:
        super().__init__(
            keyboard_type=ft.KeyboardType.PHONE,
            label="手机号",
            hint_text="请输入手机号",
            ref=ref,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
            prefix_icon=ft.icons.PHONE,
            prefix_text="+86-",
            max_length=11,
        )

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = "此栏位为必填栏位" if not control.value else None
        await control.update_async()
