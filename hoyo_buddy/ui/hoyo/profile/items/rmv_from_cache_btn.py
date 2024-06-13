from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import EnkaCache
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.enka.base import BaseClient
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import ProfileView  # noqa: F401
    from .chara_select import CharacterSelect


class RemoveFromCacheButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_from_cache.button.label"),
            style=ButtonStyle.red,
            emoji=DELETE,
            row=3,
            disabled=True,
            custom_id="profile_remove_from_cache",
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()

        assert self.view.character_id is not None
        cache = await EnkaCache.get(uid=self.view.uid)

        # Remove the character from cache
        if self.view.game is Game.STARRAIL:
            BaseClient.remove_character_from_cache(
                cache.hsr, str(self.view.character_id), enka.Game.HSR
            )
            await cache.save(update_fields=("hsr",))

        elif self.view.game is Game.GENSHIN:
            BaseClient.remove_character_from_cache(
                cache.genshin, str(self.view.character_id), enka.Game.GI
            )
            await cache.save(update_fields=("genshin",))

        # Update options in the character select
        character_select: CharacterSelect = self.view.get_item("profile_character_select")
        for option in character_select.options_before_split:
            # Remove the character from the options
            if option.value == self.view.character_id:
                character_select.options_before_split.remove(option)
                break

        character_select.options = character_select.process_options()
        self.view.character_id = str(self.view.characters[0].id)
        character_select.update_options_defaults(values=[self.view.character_id])
        character_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        await self.view.update(i, self, unset_loading_state=False)
