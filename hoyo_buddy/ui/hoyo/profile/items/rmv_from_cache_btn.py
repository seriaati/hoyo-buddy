from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord import ButtonStyle

from hoyo_buddy.db import EnkaCache
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.enka.base import BaseClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
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
        await i.response.defer()

        character_id = self.view.character_ids[0]
        cache = await EnkaCache.get(uid=self.view.uid)

        # Remove the character from cache
        if self.view.game is Game.STARRAIL:
            BaseClient.remove_character_from_cache(cache.hsr, character_id, enka.Game.HSR)
            await cache.save(update_fields=("hsr",))

        elif self.view.game is Game.GENSHIN:
            BaseClient.remove_character_from_cache(cache.genshin, character_id, enka.Game.GI)
            await cache.save(update_fields=("genshin",))

        await i.edit_original_response(
            embed=DefaultEmbed(
                self.view.locale,
                title=LocaleStr(key="set_cur_temp_as_default.done"),
                description=LocaleStr(key="remove_from_cache_finish_embed_desc"),
            ),
            view=None,
            attachments=[],
        )
