from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.emojis import REFRESH
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView


class RedrawCardButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile.redraw_card_button_label"),
            disabled=True,
            custom_id="profile_redraw_card",
            emoji=REFRESH,
            style=ButtonStyle.green,
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        await self.view.update(i, self)
