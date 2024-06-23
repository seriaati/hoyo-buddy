from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Platform

from ...components import Button, GoBackButton
from .enter_cookies_btn import EnterCookiesButton

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class WithJavaScript(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="javascript_button_label"))

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="instructions_title"),
            description=LocaleStr(key="javascript_instructions_description"),
        )
        embed.set_image(url="https://i.imgur.com/PxO0Wr6.gif")
        code = "script:document.write(document.cookie)"
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterCookiesButton(platform=Platform.HOYOLAB))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
        await i.followup.send(code, ephemeral=True)
