from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import flet as ft
import genshin
import orjson

from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.web_app.utils import show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from ..schema import Params

__all__ = ("DeviceInfoPage",)

DEVICE_INFO_APK = "https://ghproxy.mihomo.me/https://raw.githubusercontent.com/forchannot/get_device_info/main/app/build/outputs/apk/debug/app-debug.apk"
AAID_OBTAIN_APP = "https://apkpure.com/easy-advertising-id/advertising.id.ccpa.gdpr/downloading"


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
                            ft.Text(
                                "如果复制下来的 oaid 部份显示 error_123456, 则需使用 aaid。\n1. 点击下方按钮下载获取 aaid 应用程序的 apk\n2. 安装后启动并点击右下角按钮复制 aaid, 并用新复制的 aaid 取代原本的 error_123456\n结果应该长的像这样: 'oaid':'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'"
                            ),
                            ft.Row(
                                [
                                    DownloadAppButton("复制设备信息应用程序", DEVICE_INFO_APK),
                                    DownloadAppButton("获取 aaid 应用程序", AAID_OBTAIN_APP),
                                ]
                            ),
                            ft.Container(
                                DeviceInfoForm(params=params), margin=ft.margin.only(top=16)
                            ),
                        ]
                    )
                )
            ],
        )


class DownloadAppButton(ft.ElevatedButton):
    def __init__(self, text: str, url: str) -> None:
        super().__init__(text=text, icon=ft.Icons.DOWNLOAD, on_click=self.goto_download_page)
        self._url = url

    async def goto_download_page(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        page.launch_url(self._url, web_window_name=ft.UrlTarget.BLANK.value)


class DeviceInfoForm(ft.Column):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        self._login_details_ref = ft.Ref[ft.TextField]()
        self._aaid_ref = ft.Ref[AAIDField]()

        super().__init__(
            [
                DeviceInfoField(ref=self._login_details_ref),
                AAIDField(ref=self._aaid_ref),
                ft.Container(self.submit_button, margin=ft.margin.only(top=16)),
            ],
            wrap=True,
            spacing=16,
        )

    async def on_submit(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page

        device_info_field = self._login_details_ref.current
        if not device_info_field.value:
            device_info_field.error_text = "此栏位为必填栏位"
            device_info_field.update()
            return

        device_info = device_info_field.value.strip()

        try:
            device_info_dict = orjson.loads(device_info)
        except orjson.JSONDecodeError:
            show_error_banner(page, message="无效的 JSON 格式")
            return

        aaid_field = self._aaid_ref.current
        if aaid_field.value:
            aaid = aaid_field.value.strip()
            device_info_dict["oaid"] = aaid

        show_loading_snack_bar(page, message="正在提交设备信息...")
        client = ProxyGenshinClient(region=genshin.Region.CHINESE)
        device_id = device_info_dict.get("device_id", str(uuid.uuid4()).lower())

        try:
            device_fp = device_info_dict.get(
                "device_fp",
                await client.generate_fp(
                    device_id=device_id,
                    device_board=device_info_dict["deviceBoard"],
                    oaid=device_info_dict["oaid"],
                ),
            )
        except Exception as exc:
            show_error_banner(page, message=str(exc))
            return

        await page.client_storage.set_async(f"hb.{self._params.user_id}.device_id", device_id)
        await page.client_storage.set_async(f"hb.{self._params.user_id}.device_fp", device_fp)

        page.go(f"/finish?{self._params.to_query_string()}")

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
        control.update()

    async def on_field_blur(self, e: ft.ControlEvent) -> None:
        control: ft.TextField = e.control
        control.error_text = "此栏位为必填栏位" if not control.value else None
        control.update()


class AAIDField(ft.TextField):
    def __init__(self, *, ref: ft.Ref) -> None:
        super().__init__(
            keyboard_type=ft.KeyboardType.TEXT,
            label="aaid",
            hint_text="请将复制的 aaid 粘贴到此处",
            ref=ref,
        )
