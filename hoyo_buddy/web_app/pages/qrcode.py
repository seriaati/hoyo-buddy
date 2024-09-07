from __future__ import annotations

import asyncio
import pathlib
import uuid
from typing import TYPE_CHECKING

import flet as ft
import genshin
import qrcode

from hoyo_buddy.utils import dict_cookie_to_str
from hoyo_buddy.web_app.utils import encrypt_string, show_error_banner, show_loading_snack_bar

if TYPE_CHECKING:
    from ..schema import Params

__all__ = ("QRCodePage",)


class QRCodePage(ft.View):
    def __init__(self, *, params: Params) -> None:
        self._params = params
        super().__init__(
            route="/qrcode",
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text("二维码登入", size=24),
                            ft.Text(
                                "1. 点击下方按钮生成二維碼\n2. 使用米游社手机应用程序扫描二维码\n3. 在手机上点选「确认」"
                            ),
                            ft.Container(GenQRCodeButton(params), margin=ft.margin.only(top=16)),
                        ]
                    )
                )
            ],
        )


class GenQRCodeButton(ft.FilledButton):
    def __init__(self, params: Params) -> None:
        self._params = params
        super().__init__("生成二维码", on_click=self.generate_qrcode)

    async def generate_qrcode(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await show_loading_snack_bar(page, message="正在生成二维码...")

        client = genshin.Client(region=genshin.Region.CHINESE)
        result = await client._create_qrcode()

        im = qrcode.make(result.url)
        filename = uuid.uuid4().hex
        im.save(f"hoyo_buddy/web_app/assets/images/{filename}.webp")
        await page.show_dialog_async(QRCodeDialog(filename))

        scanned = False
        while True:
            try:
                status, cookies = await client._check_qrcode(result.ticket)
            except genshin.GenshinException as exc:
                await page.close_dialog_async()
                message = "二维码已过期, 请重新生成" if exc.retcode == -106 else exc.msg
                await show_error_banner(page, message=message)
                break
            except Exception as exc:
                await page.close_dialog_async()
                await show_error_banner(page, message=str(exc))
                break

            if status is genshin.models.QRCodeStatus.SCANNED and not scanned:
                await page.close_dialog_async()
                await page.show_snack_bar_async(
                    ft.SnackBar(
                        ft.Text(
                            "扫描成功, 请点击「确认登录」", color=ft.colors.ON_PRIMARY_CONTAINER
                        ),
                        bgcolor=ft.colors.PRIMARY_CONTAINER,
                    )
                )
                scanned = True
            elif status is genshin.models.QRCodeStatus.CONFIRMED:
                dict_cookies = {key: morsel.value for key, morsel in cookies.items()}
                encrypted_cookies = encrypt_string(dict_cookie_to_str(dict_cookies))
                await page.client_storage.set_async(
                    f"hb.{self._params.user_id}.cookies", encrypted_cookies
                )
                await page.go_async(f"/finish?{self._params.to_query_string()}")
                break

        # Clear the QR code image after 2 minutes
        await asyncio.sleep(2 * 60)
        path = pathlib.Path(f"hoyo_buddy/web_app/assets/images/{filename}.webp")
        if path.exists():
            path.unlink()


class QRCodeDialog(ft.AlertDialog):
    def __init__(self, filename: str) -> None:
        super().__init__(title=ft.Text("二维码"), content=ft.Image(f"/images/{filename}.webp"))
