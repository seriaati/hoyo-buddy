import logging
import pickle
from typing import TYPE_CHECKING

import mihomo

from ..constants import LOCALE_TO_MIHOMO_LANG
from ..db.models import EnkaCache

if TYPE_CHECKING:
    import discord
    from mihomo.models import Character, StarrailInfoParsed

LOGGER_ = logging.getLogger(__name__)


class MihomoAPI(mihomo.MihomoAPI):
    def __init__(self, language: "discord.Locale") -> None:
        super().__init__(LOCALE_TO_MIHOMO_LANG.get(language, mihomo.Language.EN))

    def _update_cache_with_live_data(
        self, cache: EnkaCache, live_data: "StarrailInfoParsed"
    ) -> None:
        if cache.hsr is None:
            cache.hsr = pickle.dumps(live_data)
            cache.extras.update(
                {
                    str(char.id): {"live": True, "lang": self.lang.value}
                    for char in live_data.characters
                }
            )
            return

        cache_data: StarrailInfoParsed = pickle.loads(cache.hsr)

        live_character_ids: list[str] = []
        for character in live_data.characters:
            live_character_ids.append(character.id)
            cache.extras.get(str(character.id), {}).update({"live": True, "lang": self.lang.value})

        cache_characters_not_in_live: list["Character"] = []

        for character in cache_data.characters:
            if character.id not in live_character_ids:
                cache_characters_not_in_live.append(character)
                cache.extras[str(character.id)].update({"live": False})

        cache_data.characters = cache_characters_not_in_live + live_data.characters
        cache.hsr = pickle.dumps(cache_data)

    async def fetch_user(self, uid: int) -> "StarrailInfoParsed":
        cache, _ = await EnkaCache.get_or_create(uid=uid)

        try:
            live_data = await super().fetch_user(uid, replace_icon_name_with_url=True)
        except mihomo.UserNotFound:
            if not cache.hsr:
                raise
            cache_data: StarrailInfoParsed = pickle.loads(cache.hsr)
        else:
            self._update_cache_with_live_data(cache, live_data)
            await cache.save()
            assert cache.hsr is not None

            cache_data: StarrailInfoParsed = pickle.loads(cache.hsr)

        return cache_data
