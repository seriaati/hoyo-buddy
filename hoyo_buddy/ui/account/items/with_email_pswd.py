from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed

from ...components import Button, GoBackButton
from .enter_email_pswd import EnterEmailPassword

if TYPE_CHECKING:
    from hoyo_buddy.enums import Platform
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class WithEmailPassword(Button["AccountManager"]):
    def __init__(self, platform: Platform) -> None:
        super().__init__(label=LocaleStr(key="email_password_button_label"))
        self._platform = platform

    async def callback(self, i: Interaction) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="instructions_title"),
            description=LocaleStr(key="enter_email_password_instructions_description"),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword(self._platform))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
