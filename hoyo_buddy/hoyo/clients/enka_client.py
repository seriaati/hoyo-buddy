import logging
import pickle
from typing import TYPE_CHECKING

import enka
from discord import Locale

from ...constants import LOCALE_TO_ENKA_LANG
from ...db.models import EnkaCache

if TYPE_CHECKING:
    from enka.models import Character, ShowcaseResponse

LOGGER_ = logging.getLogger(__name__)


class EnkaAPI(enka.EnkaAPI):
    def __init__(self, locale: Locale = Locale.american_english) -> None:
        super().__init__(LOCALE_TO_ENKA_LANG.get(locale, enka.Language.ENGLISH))

    async def __aenter__(self) -> "EnkaAPI":
        await super().__aenter__()
        return self

    def _update_cache_with_live_data(self, cache: EnkaCache, live_data: "ShowcaseResponse") -> None:
        """
        Updates the cache with live data.

        Args:
            cache (EnkaCache): The cache object to update.
            live_data (ShowcaseResponse): The live data to update the cache with.
        """
        live_chara_data = {"live": True, "lang": self._lang.value}

        if cache.genshin is None:
            cache.genshin = pickle.dumps(live_data)
            cache.extras.update({str(char.id): live_chara_data for char in live_data.characters})
            return

        cache_data: ShowcaseResponse = pickle.loads(cache.genshin)

        live_character_ids: list[int] = []
        for character in live_data.characters:
            live_character_ids.append(character.id)
            if str(character.id) not in cache.extras:
                cache.extras[str(character.id)] = live_chara_data
            else:
                cache.extras[str(character.id)].update(live_chara_data)

        cache_characters_not_in_live: list["Character"] = []

        for character in cache_data.characters:
            if character.id not in live_character_ids:
                cache_characters_not_in_live.append(character)
                cache.extras[str(character.id)].update({"live": False})

        cache_data.characters = cache_characters_not_in_live + live_data.characters
        cache.genshin = pickle.dumps(cache_data)

    def _set_all_live_to_false(self, cache: EnkaCache) -> None:
        """
        Sets the 'live' attribute of all characters in the cache to False.

        Args:
            cache (EnkaCache): The cache object containing the character data.

        Returns:
            None
        """
        if cache.genshin is None:
            return

        cache_data: ShowcaseResponse = pickle.loads(cache.genshin)
        for character in cache_data.characters:
            cache.extras[str(character.id)].update({"live": False})

    def get_character_talent_order(self, character_id: str) -> list[int]:
        if self._assets is None:
            msg = "Assets not loaded"
            raise RuntimeError(msg)

        if character_id not in self._assets.character_data:
            msg = f"Character ID {character_id} not found in Enka character data"
            raise ValueError(msg)

        return self._assets.character_data[character_id]["SkillOrder"]

    async def fetch_showcase(self, uid: int) -> "ShowcaseResponse":
        cache, _ = await EnkaCache.get_or_create(uid=uid)

        try:
            live_data = await super().fetch_showcase(uid)
        except enka.exceptions.GameMaintenanceError:
            if cache.genshin is None:
                raise

            self._set_all_live_to_false(cache)
            await cache.save()
            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)
        else:
            self._update_cache_with_live_data(cache, live_data)
            await cache.save()
            assert cache.genshin is not None

            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)

        return cache_data
