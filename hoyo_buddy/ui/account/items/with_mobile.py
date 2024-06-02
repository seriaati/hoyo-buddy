from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr

from ....embeds import DefaultEmbed
from ...components import Button, GoBackButton
from .enter_mobile import EnterPhoneNumber

if TYPE_CHECKING:
    from ....bot.bot import INTERACTION
    from ..view import AccountManager  # noqa: F401


class WithMobileNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="with_mobile_number",
            label=LocaleStr("With phone number", key="add_miyoushe_acc.with_mobile_number"),
        )

    async def callback(self, i: INTERACTION) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    "1. Click the button below to enter your phone number\n"
                    "2. You will receive a verification code via SMS\n"
                    "3. Click the button below to enter the verification code\n"
                ),
                key="mobile_instructions_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterPhoneNumber())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
