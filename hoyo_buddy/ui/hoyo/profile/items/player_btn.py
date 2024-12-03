from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.emojis import BOOK_MULTIPLE
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
    from .chara_select import CharacterSelect
else:
    ProfileView = None


class PlayerInfoButton(Button[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.player_info.button.label"),
            style=ButtonStyle.blurple,
            emoji=BOOK_MULTIPLE,
            disabled=True,
            custom_id="profile_player_info",
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        self.disabled = True

        disable_btns = (
            "profile_card_settings",
            "profile_image_settings",
            "profile_team_card_settings",
            "profile_build_select",
            "profile_redraw_card",
        )
        for btn in disable_btns:
            button = self.view.get_item(btn)
            button.disabled = True

        chara_select: CharacterSelect = self.view.get_item("profile_character_select")
        chara_select.update_options_defaults(values=["none"])

        await i.response.edit_message(embed=self.view.player_embed, attachments=[], view=self.view)
