import logging
import pickle
from typing import TYPE_CHECKING

import enka
from discord import Locale

from ...constants import ENKA_LANG_TO_LOCALE, LOCALE_TO_ENKA_LANG
from ...db.models import EnkaCache
from .base import BaseClient

if TYPE_CHECKING:
    from enka.models import ShowcaseResponse

LOGGER_ = logging.getLogger(__name__)


class EnkaAPI(enka.EnkaAPI, BaseClient):
    def __init__(self, locale: Locale = Locale.american_english) -> None:
        lang = LOCALE_TO_ENKA_LANG.get(locale, enka.Language.ENGLISH)
        super().__init__(lang=lang)
        self.locale = ENKA_LANG_TO_LOCALE[lang]

    async def __aenter__(self) -> "EnkaAPI":
        await super().__aenter__()
        return self

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

            cache.extras = self._set_all_live_to_false(cache.genshin, cache.extras)
            await cache.save(update_fields=("extras",))
            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)
        else:
            cache.genshin, cache.extras = self._update_cache_with_live_data(
                cache.genshin, cache.extras, live_data, self.locale
            )
            await cache.save(update_fields=("genshin", "extras"))
            cache_data: ShowcaseResponse = pickle.loads(cache.genshin)

        return cache_data
