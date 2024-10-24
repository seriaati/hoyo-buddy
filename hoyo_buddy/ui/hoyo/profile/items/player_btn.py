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

        card_settings_btn = self.view.get_item("profile_card_settings")
        card_settings_btn.disabled = True

        image_settings_btn = self.view.get_item("profile_image_settings")
        image_settings_btn.disabled = True

        # Enable the team card settings button
        team_card_settings_btn = self.view.get_item("profile_team_card_settings")
        team_card_settings_btn.disabled = False

        chara_select: CharacterSelect = self.view.get_item("profile_character_select")
        chara_select.update_options_defaults(values=["none"])

        build_select = self.view.get_item("profile_build_select")
        build_select.disabled = True

        redraw_card_btn = self.view.get_item("profile_redraw_card")
        redraw_card_btn.disabled = True

        await i.response.edit_message(embed=self.view.player_embed, attachments=[], view=self.view)
