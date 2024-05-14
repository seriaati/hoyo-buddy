from __future__ import annotations

import logging
import pickle
from typing import TYPE_CHECKING

import enka

from ...constants import ENKA_HSR_LANG_TO_LOCALE, LOCALE_TO_ENKA_HSR_LANG
from ...db.models import EnkaCache
from .base import BaseClient

if TYPE_CHECKING:
    import discord
    from enka.hsr import ShowcaseResponse

LOGGER_ = logging.getLogger(__name__)


class MihomoAPI(enka.HSRClient, BaseClient):
    def __init__(self, locale: discord.Locale) -> None:
        lang = LOCALE_TO_ENKA_HSR_LANG.get(locale, enka.hsr.Language.ENGLISH)
        super().__init__(lang=lang)
        self.locale = ENKA_HSR_LANG_TO_LOCALE[lang]

    async def fetch_user(self, uid: int) -> ShowcaseResponse:
        cache, _ = await EnkaCache.get_or_create(uid=uid)

        try:
            live_data = await super().fetch_showcase(uid)
        except enka.errors.GameMaintenanceError:
            if not cache.hsr:
                raise

            cache.extras = self._set_all_live_to_false(cache.hsr, cache.extras)
            await cache.save(update_fields=("extras",))
            cache_data: ShowcaseResponse = pickle.loads(cache.hsr)
        else:
            cache.hsr, cache.extras = self._update_cache_with_live_data(
                cache.hsr, cache.extras, live_data, self.locale
            )
            await cache.save(update_fields=("hsr", "extras"))
            cache_data: ShowcaseResponse = pickle.loads(cache.hsr)

        return cache_data
