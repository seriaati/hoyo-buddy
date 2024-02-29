import logging

import discord
import mihomo

from ..db.models import EnkaCache

LOCALE_TO_MIHOMO_LANG: dict[discord.Locale, mihomo.Language] = {
    discord.Locale.taiwan_chinese: mihomo.Language.CHT,
    discord.Locale.chinese: mihomo.Language.CHS,
    discord.Locale.german: mihomo.Language.DE,
    discord.Locale.american_english: mihomo.Language.EN,
    discord.Locale.spain_spanish: mihomo.Language.ES,
    discord.Locale.french: mihomo.Language.FR,
    discord.Locale.indonesian: mihomo.Language.ID,
    discord.Locale.japanese: mihomo.Language.JP,
    discord.Locale.korean: mihomo.Language.KR,
    discord.Locale.brazil_portuguese: mihomo.Language.PT,
    discord.Locale.russian: mihomo.Language.RU,
    discord.Locale.thai: mihomo.Language.TH,
    discord.Locale.vietnamese: mihomo.Language.VI,
}

LOGGER_ = logging.getLogger(__name__)


class MihomoAPI(mihomo.MihomoAPI):
    def __init__(self, language: discord.Locale) -> None:
        super().__init__(LOCALE_TO_MIHOMO_LANG.get(language, mihomo.Language.EN))

    def _update_cache_with_live_data(
        self, cache: EnkaCache, live_data: mihomo.StarrailInfoParsed
    ) -> None:
        cache_player = cache.hsr.get("player", {})
        cache_player.update(live_data.player.model_dump(by_alias=True))
        cache.hsr["player"] = cache_player

        cache_characters = cache.hsr.get("characters", [])
        for character in live_data.characters:
            for c in cache_characters:
                if c["id"] == character.id:
                    c.update(character.model_dump(by_alias=True))
                    break
            else:
                cache_characters.append(character.model_dump(by_alias=True))
        cache.hsr["characters"] = cache_characters

    async def fetch_user(self, uid: int) -> tuple[mihomo.StarrailInfoParsed, list[str]]:
        cache, _ = await EnkaCache.get_or_create(uid=uid)
        live_data_character_ids: list[str] = []

        try:
            live_data = await super().fetch_user(uid, replace_icon_name_with_url=True)
        except mihomo.UserNotFound:
            if not cache.hsr:
                raise
            cache_data = mihomo.StarrailInfoParsed(**cache.hsr)
        else:
            live_data_character_ids.extend([char.id for char in live_data.characters])
            self._update_cache_with_live_data(cache, live_data)
            await cache.save()

            try:
                cache_data = mihomo.StarrailInfoParsed(**cache.hsr)
            except Exception:
                LOGGER_.exception("Failed to parse cache data")
                cache_data = live_data

        return cache_data, live_data_character_ids
