from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

from ...components import Button, GoBackButton
from .enter_mobile import EnterPhoneNumber

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class WithMobileNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="with_mobile_number",
            label=LocaleStr(key="add_miyoushe_acc.with_mobile_number"),
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="instructions_title"),
            description=LocaleStr(key="mobile_instructions_description"),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))

        self.view.clear_items()
        self.view.add_item(EnterPhoneNumber())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
