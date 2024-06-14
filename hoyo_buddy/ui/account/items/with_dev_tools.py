from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed

from ...components import Button, GoBackButton
from .enter_cookies_btn import EnterCookiesButton

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction
    from hoyo_buddy.enums import Platform

    from ..view import AccountManager  # noqa: F401


class WithDevTools(Button["AccountManager"]):
    def __init__(self, platform: Platform) -> None:
        super().__init__(label=LocaleStr(key="devtools_button_label"))
        self._platform = platform

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="instructions_title"),
            description=LocaleStr(key="devtools_instructions_description"),
        )
        embed.set_image(url="https://i.imgur.com/HWMZhVe.gif")
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterCookiesButton(platform=self._platform, dev_tools=True))
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
