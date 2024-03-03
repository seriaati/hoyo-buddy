import logging
import pickle
from typing import TYPE_CHECKING

import enka

from ..constants import LOCALE_TO_ENKA_LANG
from ..db.models import EnkaCache

if TYPE_CHECKING:
    import discord
    from enka.models import Character, ShowcaseResponse

LOGGER_ = logging.getLogger(__name__)


class EnkaAPI(enka.EnkaAPI):
    def __init__(self, locale: "discord.Locale") -> None:
        super().__init__(LOCALE_TO_ENKA_LANG.get(locale, enka.Language.ENGLISH))

    async def __aenter__(self) -> "EnkaAPI":
        await super().__aenter__()
        return self

    def _update_cache_with_live_data(self, cache: EnkaCache, live_data: "ShowcaseResponse") -> None:
        if cache.genshin is None:
            cache.genshin = pickle.dumps(live_data)
            cache.extras.update(
                {
                    str(char.id): {"live": True, "lang": self._lang.value}
                    for char in live_data.characters
                }
            )
            return

        cache_data: ShowcaseResponse = pickle.loads(cache.genshin)

        live_character_ids: list[int] = []
        for character in live_data.characters:
            live_character_ids.append(character.id)
            cache.extras[str(character.id)].update({"live": True, "lang": self._lang.value})

        cache_characters_not_in_live: list["Character"] = []

        for character in cache_data.characters:
            if character.id not in live_character_ids:
                cache_characters_not_in_live.append(character)
                cache.extras[str(character.id)].update({"live": False})

        cache_data.characters = cache_characters_not_in_live + live_data.characters
        cache.genshin = pickle.dumps(cache_data)

    async def fetch_showcase(self, uid: int) -> "ShowcaseResponse":
        cache, _ = await EnkaCache.get_or_create(uid=uid)

        try:
            live_data = await super().fetch_showcase(uid)
        except enka.exceptions.GameMaintenanceError:
            if cache.genshin is None:
                raise
            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)
        else:
            self._update_cache_with_live_data(cache, live_data)
            await cache.save()
            assert cache.genshin is not None

            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)

        return cache_data
