from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

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
                            ft.Text(
                                "1.点击下方按钮输入手机号\n2.你将会收到短信验证码\n3.点击下方按钮填写验证码"
                            ),
                            ft.Container(
                                MobileNumberForm(params=params), margin=ft.margin.only(top=16)
                            ),
                            ft.Container(
                                VerificationCodeForm(params=params), margin=ft.margin.only(top=16)
                            ),
                        ]
                    )
                )
            ],
        )


class MobileNumberForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._mobile_number_ref = ft.Ref[ft.TextField]()

        super().__init__(
            [MobileNumberField(ref=self._mobile_number_ref), self.submit_button],
            wrap=True,
            spacing=16,
        )

    async def on_submit(self, _: ft.ControlEvent) -> None:
        login_details = self._mobile_number_ref.current
        if not login_details.value:
            login_details.error_text = "此栏位为必填栏位"
            await login_details.update_async()

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


class VerificationCodeForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._verification_code_ref = ft.Ref[ft.TextField]()

        super().__init__(
            [VerificationCodeField(ref=self._verification_code_ref), self.submit_button],
            wrap=True,
            spacing=16,
        )

    async def on_submit(self, _: ft.ControlEvent) -> None:
        login_details = self._verification_code_ref.current
        if not login_details.value:
            login_details.error_text = "此栏位为必填栏位"
            await login_details.update_async()

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(text="提交", on_click=self.on_submit)


class VerificationCodeField(ft.TextField):
    def __init__(self, *, ref: ft.Ref) -> None:
        super().__init__(
            keyboard_type=ft.KeyboardType.PHONE,
            label="验证码",
            hint_text="请输入验证码",
            ref=ref,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
            prefix_icon=ft.icons.NUMBERS,
            max_length=6,
        )

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = "此栏位为必填栏位" if not control.value else None
        control.error_text = (
            "验证码应为6位数字" if control.value and len(control.value) != 6 else None
        )
        await control.update_async()
