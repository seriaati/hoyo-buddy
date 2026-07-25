from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.db import Settings
from hoyo_buddy.db.utils import get_card_settings
from hoyo_buddy.emojis import PHOTO
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button
from hoyo_buddy.ui.settings.view import CardSettingsCategory, CardSettingsView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None


class ImageSettingsButton(Button[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.image_settings.button.label"),
            disabled=True,
            custom_id="profile_image_settings",
            emoji=PHOTO,
            style=ButtonStyle.blurple,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()

        character_id = self.view.character_ids[0]
        card_settings = await get_card_settings(i.user.id, character_id, game=self.view.game)
        settings = await Settings.get(user_id=i.user.id)
        character = self.view.characters[character_id]
        view = CardSettingsView(
            card_settings=card_settings,
            settings=settings,
            character_name=character.name,
            game=self.view.game,
            author=i.user,
            locale=self.view.locale,
            character=character,
            category=CardSettingsCategory.IMAGE,
            image_type="team_card_image"
            if len(self.view.character_ids) > 1
            else "build_card_image",
        )
        await view.update(i, followup=True)
