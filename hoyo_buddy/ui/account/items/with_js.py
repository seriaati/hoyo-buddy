from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.enums import Platform

from ...components import Button, GoBackButton
from .enter_cookies_btn import EnterCookiesButton

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import AccountManager  # noqa: F401


class WithJavaScript(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr("With JavaScript", key="javascript_button_label"))

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{INFO} Note: This method should work for all major browsers on desktop, but on mobile, it only works for **Chrome** and **Edge**.\n\n"
                    "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (for CN players)\n"
                    "2. Copy the code below\n"
                    "3. Click on the address bar and type `java`\n"
                    "4. Paste the code and press enter. Make sure there are **NO SPACES** between `java` and `script`\n"
                    "5. Select all and copy the text that appears\n"
                    "6. Click the button below and paste the text in the box\n"
                ),
                key="javascript_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/PxO0Wr6.gif")
        code = "script:document.write(document.cookie)"
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterCookiesButton(platform=Platform.HOYOLAB))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
        await i.followup.send(code, ephemeral=True)
