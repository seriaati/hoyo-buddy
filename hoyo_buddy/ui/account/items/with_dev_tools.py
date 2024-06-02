from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed

from ...components import Button, GoBackButton
from .enter_cookies_btn import EnterCookiesButton

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ....enums import Platform
    from ..view import AccountManager  # noqa: F401


class WithDevTools(Button["AccountManager"]):
    def __init__(self, platform: Platform) -> None:
        super().__init__(
            label=LocaleStr("With DevTools (desktop only)", key="devtools_button_label")
        )
        self._platform = platform

    async def callback(self, i: INTERACTION) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (for CN players)\n"
                    "2. Open the DevTools by pressing F12 or Ctrl+Shift+I\n"
                    "3. Press the >> icon on the top navigation bar\n"
                    "4. Click on the `Application` tab\n"
                    "5. Click on `Cookies` on the left sidebar\n"
                    "6. Click on the website you're on (e.g. https://www.hoyolab.com)\n"
                    "7. Type `v2` in the `Filter` box\n"
                    "8. Click the button below\n"
                    "9. Copy the `Value` of each cookie and paste them in the boxes\n"
                ),
                key="devtools_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/HWMZhVe.gif")
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterCookiesButton(platform=self._platform, dev_tools=True))
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
