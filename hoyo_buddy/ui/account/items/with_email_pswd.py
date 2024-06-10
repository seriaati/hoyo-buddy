from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO

from ...components import Button, GoBackButton
from .enter_email_pswd import EnterEmailPassword

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction
    from hoyo_buddy.enums import Platform

    from ..view import AccountManager  # noqa: F401


class WithEmailPassword(Button["AccountManager"]):
    def __init__(self, platform: Platform) -> None:
        super().__init__(
            label=LocaleStr("With email and password", key="email_password_button_label")
        )
        self._platform = platform

    async def callback(self, i: Interaction) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                f"{INFO} This method requires you to enter your private information.\n\n"
                "• In exchange, your `cookie_token` can be refreshed automatically, which is used in features related to code redemption (for HoYoLAB users only).\n"
                "• Your email and password are **NOT** saved in the database **AT ALL**, so it's practically impossible for them to be leaked.\n"
                "• Additionally, this bot is open-sourced on [GitHub](https://github.com/seriaati/hoyo-buddy), so you can verify that yourself.\n"
                "• It is ultimately your choice to decide whether to trust this bot or not.\n\n"
                "Click on the button below to start.\n",
                key="enter_email_password_instructions_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword(self._platform))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
