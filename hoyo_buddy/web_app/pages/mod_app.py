from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from hoyo_buddy.utils import dict_cookie_to_str, str_cookie_to_dict
from hoyo_buddy.web_app.utils import encrypt_string

if TYPE_CHECKING:
    from ..schema import Params

__all__ = ("ModAppPage",)


class ModAppPage(ft.View):
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
                                "1. 如果你的装置上已经有米游社的应用程序, 请将它卸载。\n2. 点击下方的按钮下载改装过的应用程序档案。\n3. 安装该应用程序, 并启动它。\n4. 忽略任何更新视窗, 登入你的帐户。\n5. 点击「我的」并点击钥匙图案。\n6. 点击「复制登入信息」。\n7. 点击下方的「通过改装过的米游社应用程序」按钮并将复制的登入信息贴上。"
                            ),
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                DownloadAppButton(),
                                                ft.ElevatedButton(
                                                    "教程", on_click=lambda e: e.page.open(ShowImageDialog())
                                                ),
                                            ],
                                            wrap=True,
                                        ),
                                        LoginDetailForm(params=params),
                                    ],
                                    wrap=True,
                                    spacing=16,
                                ),
                                margin=ft.margin.only(top=16),
                            ),
                        ]
                    )
                )
            ],
        )


class DownloadAppButton(ft.ElevatedButton):
    def __init__(self) -> None:
        super().__init__(text="下载应用程序", icon=ft.icons.DOWNLOAD, on_click=self.goto_download_page)

    async def goto_download_page(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.launch_url_async(
            "https://github.com/PaiGramTeam/GetToken/releases/latest/download/miyoushe-361-lspatched.apk",
            web_window_name=ft.UrlTarget.BLANK.value,
        )


class ShowImageDialog(ft.AlertDialog):
    def __init__(self) -> None:
        super().__init__(
            content=ft.Column(
                [
                    ft.Image(
                        src="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial1.jpg",
                        border_radius=8,
                    ),
                    ft.Image(
                        src="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial2.jpg",
                        border_radius=8,
                    ),
                ],
                tight=True,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: e.page.close(self))],
        )


class LoginDetailForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._login_details_ref = ft.Ref[ft.TextField]()

        super().__init__([LoginDetailField(ref=self._login_details_ref), ft.Container(self.submit_button)], spacing=16)

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        login_details = self._login_details_ref.current
        if not login_details.value:
            login_details.error_text = "此栏位为必填栏位"
            await login_details.update_async()
            return

        dict_cookies = str_cookie_to_dict(login_details.value)
        device_id = dict_cookies.pop("x-rpc-device_id", None)
        device_fp = dict_cookies.pop("x-rpc-device_fp", None)
        if device_id is not None:
            await page.client_storage.set_async(f"hb.{self._params.user_id}.device_id", device_id)
        if device_fp is not None:
            await page.client_storage.set_async(f"hb.{self._params.user_id}.device_fp", device_fp)

        cookies = dict_cookie_to_str(dict_cookies)
        encrypted_cookies = encrypt_string(cookies)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.cookies", encrypted_cookies)
        await page.go_async(f"/finish?{self._params.to_query_string()}")

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(text="提交", on_click=self.on_submit)


class LoginDetailField(ft.TextField):
    def __init__(self, *, ref: ft.Ref) -> None:
        super().__init__(
            keyboard_type=ft.KeyboardType.TEXT,
            label="登录信息",
            hint_text="请将复制的登录信息粘贴到此处",
            ref=ref,
            on_blur=self.on_field_blur,
            on_focus=self.on_field_focus,
            multiline=True,
        )

    async def on_field_focus(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = None
        await control.update_async()

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = "此栏位为必填栏位" if not control.value else None
        await control.update_async()
