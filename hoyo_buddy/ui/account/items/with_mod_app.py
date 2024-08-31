from __future__ import annotations

from typing import TYPE_CHECKING, Any

import genshin
from discord import ButtonStyle, TextStyle

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Platform

from ...components import Button, GoBackButton, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class WithModApp(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(label="通过改装过的米游社应用程序")

    @property
    def _instructions_embed(self) -> list[DefaultEmbed]:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="指引",
            description="1. 如果你的装置上已经有米游社的应用程序, 请将它卸载。\n2. 点击下方的按钮下载改装过的应用程序档案。\n3. 安装该应用程序, 并启动它。\n4. 忽略任何更新视窗, 登入你的帐户。\n5. 点击「我的」并点击钥匙图案。\n6. 点击「复制登入信息」。\n7. 点击下方的「通过改装过的米游社应用程序」按钮并将复制的登入信息贴上。",
            url="https://github.com/seriaati/hoyo-buddy",
        )
        embed.set_image(
            url="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial1.jpg"
        )
        embed2 = embed.copy()
        embed2.set_image(
            url="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial2.jpg"
        )
        return [embed, embed2]

    async def callback(self, i: Interaction) -> Any:
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(go_back_button)
        self.view.add_item(
            Button(
                label="下载应用程序",
                url="https://github.com/PaiGramTeam/GetToken/releases/latest/download/miyoushe-361-lspatched.apk",
            )
        )
        self.view.add_item(EnterLoginDetails())
        await i.response.edit_message(embeds=self._instructions_embed, view=self.view)


class LoginDetailModal(Modal):
    login_detail = TextInput(label="登录信息", style=TextStyle.long)


class EnterLoginDetails(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(label="输入登录信息", style=ButtonStyle.primary)

    async def callback(self, i: Interaction) -> Any:
        self.view.clear_items()
        self.view.add_item(GoBackButton(self.view.children, self.view.get_embeds(i.message)))

        modal = LoginDetailModal(title="输入登录信息")
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        cookies = genshin.parse_cookie(modal.login_detail.value)
        await self.view.finish_cookie_setup(cookies, platform=Platform.MIYOUSHE, interaction=i)
