import logging
import pickle
from typing import TYPE_CHECKING

import mihomo

from ...constants import LOCALE_TO_MIHOMO_LANG, MIHOMO_LANG_TO_LOCALE
from ...db.models import EnkaCache
from .base import BaseClient

if TYPE_CHECKING:
    import discord
    from mihomo.models import StarrailInfoParsed

LOGGER_ = logging.getLogger(__name__)


class MihomoAPI(mihomo.MihomoAPI, BaseClient):
    def __init__(self, locale: "discord.Locale") -> None:
        lang = LOCALE_TO_MIHOMO_LANG.get(locale, mihomo.Language.EN)
        super().__init__(language=lang)
        self.locale = MIHOMO_LANG_TO_LOCALE[lang]

    async def fetch_user(self, uid: int) -> "StarrailInfoParsed":
        cache, _ = await EnkaCache.get_or_create(uid=uid)

        try:
            live_data = await super().fetch_user(uid, replace_icon_name_with_url=True)
        except mihomo.UserNotFound:
            if not cache.hsr:
                raise

            cache.extras = self._set_all_live_to_false(cache.hsr, cache.extras)
            await cache.save()
            cache_data: StarrailInfoParsed = pickle.loads(cache.hsr)
        else:
            cache.hsr, cache.extras = self._update_cache_with_live_data(
                cache.hsr, cache.extras, live_data, self.locale
            )
            await cache.save()
            cache_data: StarrailInfoParsed = pickle.loads(cache.hsr)

        return cache_data
