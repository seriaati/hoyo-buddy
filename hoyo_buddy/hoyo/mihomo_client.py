import logging
from typing import TYPE_CHECKING

import mihomo

from ..constants import LOCALE_TO_MIHOMO_LANG
from ..db.models import EnkaCache
from .dataclasses import ExtendedStarRailInfoParsed

if TYPE_CHECKING:
    import discord

LOGGER_ = logging.getLogger(__name__)


class MihomoAPI(mihomo.MihomoAPI):
    def __init__(self, language: "discord.Locale") -> None:
        super().__init__(LOCALE_TO_MIHOMO_LANG.get(language, mihomo.Language.EN))

    def _update_cache_with_live_data(
        self, cache: EnkaCache, live_data: mihomo.StarrailInfoParsed
    ) -> None:
        cache_player = cache.hsr.get("player", {})
        cache_player.update(live_data.player.model_dump(by_alias=True))
        cache.hsr["player"] = cache_player

        cache_characters = cache.hsr.get("characters", [])
        for character in live_data.characters:
            model_dump = character.model_dump(by_alias=True)
            model_dump["lang"] = self.lang.value

            for c in cache_characters:
                if c["id"] == character.id:
                    c.update(model_dump)
                    break
            else:
                cache_characters.append(model_dump)
        cache.hsr["characters"] = cache_characters

    async def fetch_user(self, uid: int) -> ExtendedStarRailInfoParsed:
        cache, _ = await EnkaCache.get_or_create(uid=uid)
        live_data_character_ids: list[str] = []

        try:
            live_data = await super().fetch_user(uid, replace_icon_name_with_url=True)
        except mihomo.UserNotFound:
            if not cache.hsr:
                raise
            cache_data = ExtendedStarRailInfoParsed(**cache.hsr)
        else:
            live_data_character_ids.extend([char.id for char in live_data.characters])
            self._update_cache_with_live_data(cache, live_data)
            await cache.save()

            cache_data = ExtendedStarRailInfoParsed(**cache.hsr)

        for character in cache_data.characters:
            character.live = character.id in live_data_character_ids
            character.lang = next(
                (c["lang"] for c in cache.hsr["characters"] if c["id"] == character.id),
                self.lang.value,
            )

        return cache_data
