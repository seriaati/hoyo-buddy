from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.emojis import SETTINGS
from hoyo_buddy.enums import CharacterType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button
from hoyo_buddy.ui.hoyo.profile.card_settings import CardSettingsView, get_card_settings

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView  # noqa: F401


class CardSettingsButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile.card_settings.button.label"),
            disabled=True,
            custom_id="profile_card_settings",
            emoji=SETTINGS,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        character_id = self.view.character_ids[0]
        card_settings = await get_card_settings(i.user.id, character_id, game=self.view.game)
        view = CardSettingsView(
            list(self.view.characters.values()),
            character_id,
            self.view._card_data,
            card_settings,
            self.view.game,
            self.view.character_type is CharacterType.CACHE,
            len(self.view.character_ids) > 1,
            author=i.user,
            locale=self.view.locale,
            translator=self.view.translator,
        )
        await view.start(i)
