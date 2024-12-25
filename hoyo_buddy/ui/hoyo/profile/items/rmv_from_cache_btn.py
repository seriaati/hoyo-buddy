from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord import ButtonStyle

from hoyo_buddy.db import EnkaCache
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.enka.base import BaseClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
    from .chara_select import CharacterSelect
else:
    ProfileView = None


class RemoveFromCacheButton(Button[ProfileView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_from_cache.button.label"),
            style=ButtonStyle.red,
            emoji=DELETE,
            disabled=True,
            custom_id="profile_remove_from_cache",
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        character_id = self.view.character_ids[0]
        cache = await EnkaCache.get(uid=self.view.uid)

        # Remove the character from cache
        if self.view.game is Game.STARRAIL:
            BaseClient.remove_character_from_cache(cache.hsr, character_id, enka.Game.HSR)
            await cache.save(update_fields=("hsr",))

        elif self.view.game is Game.GENSHIN:
            BaseClient.remove_character_from_cache(cache.genshin, character_id, enka.Game.GI)
            await cache.save(update_fields=("genshin",))

        # Update options in the character select
        character_select: CharacterSelect = self.view.get_item("profile_character_select")
        for option in character_select.options_before_split:
            # Remove the character from the options
            if option.value == character_id:
                character_select.options_before_split.remove(option)
                break

        character_select.options = character_select.process_options()
        first_character_id = next(iter(self.view.characters.keys()), None)
        if first_character_id is not None:
            self.view.character_ids = [first_character_id]
        character_select.update_options_defaults(values=[character_id])
        character_select.translate(self.view.locale)

        # Redraw the card
        await self.view.update(i, self, unset_loading_state=False)
