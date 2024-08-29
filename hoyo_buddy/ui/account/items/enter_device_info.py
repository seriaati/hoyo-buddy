import json
import uuid
from typing import TYPE_CHECKING, Any

import genshin
from discord import ButtonStyle, TextStyle

from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.enums import Platform
from hoyo_buddy.ui import Button, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class DeviceInfoModal(Modal):
    device_info = TextInput(label="设备信息", style=TextStyle.long)


class EnterDeviceInfoButton(Button["AccountManager"]):
    def __init__(self, cookies: dict[str, Any]) -> None:
        super().__init__(label="提交设备信息", style=ButtonStyle.blurple)
        self._cookies = cookies

    @staticmethod
    def get_embed(view: "AccountManager") -> DefaultEmbed:
        embed = DefaultEmbed(
            view.locale,
            view.translator,
            title="需要补充设备信息",
            description="1. 点击下方按钮下载用于获取设备信息的应用程序\n2. 安装并启动该应用\n3. 点击「点击查看信息」\n4. 点击「点击复制」\n5. 点击下方的「提交设备信息」按钮并将复制的信息贴上",
        )
        return embed

    async def callback(self, i: "Interaction") -> None:
        modal = DeviceInfoModal(title="提交设备信息")
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        try:
            device_info = json.loads(modal.device_info.value.strip())
        except json.JSONDecodeError:
            await i.followup.send(
                embed=ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title="错误",
                    description="无法解析设备信息",
                ),
            )
            return

        client = genshin.Client(region=genshin.Region.CHINESE)
        device_id = str(uuid.uuid4()).lower()
        device_fp = await client.generate_fp(
            device_id=device_id, device_board=device_info["deviceBoard"], oaid=device_info["oaid"],
        )
        self._cookies["x-rpc-device_id"] = device_id
        self._cookies["x-rpc-device_fp"] = device_fp

        await self.view.finish_cookie_setup(
            self._cookies, platform=Platform.MIYOUSHE, interaction=i,
        )
