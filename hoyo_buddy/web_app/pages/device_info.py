from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import flet as ft
import genshin
import orjson

from hoyo_buddy.web_app.utils import show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from ..schema import Params

__all__ = ("DeviceInfoPage",)


class DeviceInfoPage(ft.View):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        super().__init__(
            route="/mod_app",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text("需要补充设备信息", size=24),
                            ft.Text(
                                "1. 点击下方按钮下载用于获取设备信息的应用程序\n2. 安装并启动该应用\n3. 点击「点击查看信息」\n4. 点击「点击复制」\n5. 点击下方的「提交设备信息」按钮并将复制的信息贴上"
                            ),
                            DownloadAppButton(),
                            ft.Container(
                                DeviceInfoForm(params=params), margin=ft.margin.only(top=16)
                            ),
                        ]
                    )
                )
            ],
        )


class DownloadAppButton(ft.ElevatedButton):
    def __init__(self) -> None:
        super().__init__(
            text="下载应用程序", icon=ft.icons.DOWNLOAD, on_click=self.goto_download_page
        )

    async def goto_download_page(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.launch_url_async(
            "https://mirror.ghproxy.com/https://raw.githubusercontent.com/forchannot/get_device_info/main/app/build/outputs/apk/debug/app-debug.apk",
            web_window_name=ft.UrlTarget.BLANK.value,
        )


class DeviceInfoForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._login_details_ref = ft.Ref[ft.TextField]()

        super().__init__(
            [
                DeviceInfoField(ref=self._login_details_ref),
                ft.Container(self.submit_button, margin=ft.margin.only(top=16)),
            ],
            wrap=True,
            spacing=16,
        )

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        device_info = self._login_details_ref.current
        if not device_info.value:
            device_info.error_text = "此栏位为必填栏位"
            await device_info.update_async()
            return

        try:
            device_info = orjson.loads(device_info.value.strip())
        except orjson.JSONDecodeError:
            await show_error_banner(page, message="无效的 JSON 格式")
            return

        await show_loading_snack_bar(page, message="正在提交设备信息...")
        client = genshin.Client(region=genshin.Region.CHINESE)
        device_id = str(uuid.uuid4()).lower()
        try:
            device_fp = await client.generate_fp(
                device_id=device_id,
                device_board=device_info["deviceBoard"],
                oaid=device_info["oaid"],
            )
        except Exception as exc:
            await show_error_banner(page, message=str(exc))
            return

        await page.client_storage.set_async(f"hb.{self._params.user_id}.device_id", device_id)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.device_fp", device_fp)

        await page.go_async(f"/finish?{self._params.to_query_string()}")

    @property
    def submit_button(self) -> ft.FilledButton:
        return ft.FilledButton(text="提交", on_click=self.on_submit)


class DeviceInfoField(ft.TextField):
    def __init__(self, *, ref: ft.Ref) -> None:
        super().__init__(
            keyboard_type=ft.KeyboardType.TEXT,
            label="设备信息",
            hint_text="请将复制的设备信息粘贴到此处",
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
