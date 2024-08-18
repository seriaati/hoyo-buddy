from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed

from ...components import Button, GoBackButton
from .enter_mobile import EnterPhoneNumber

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class WithMobileNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(custom_id="with_mobile_number", label="通过手机号")

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="指引",
            description="1.点击下方按钮输入手机号\n2.你将会收到短信验证码\n3.点击下方按钮填写验证码",
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterPhoneNumber())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
