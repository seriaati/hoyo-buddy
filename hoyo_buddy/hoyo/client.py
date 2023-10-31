from typing import Optional

import genshin
from discord import Locale

from ..bot.embeds import DefaultEmbed
from ..bot.translator import Translator
from ..bot.translator import locale_str as _T
from ..db.enums import GAME_THUMBNAILS

LOCALE_CONVERTER = {
    Locale.british_english: "en-us",
    Locale.american_english: "en-us",
    Locale.taiwan_chinese: "zh-tw",
    Locale.chinese: "zh-cn",
    Locale.german: "de-de",
    Locale.spain_spanish: "es-es",
    Locale.french: "fr-fr",
    Locale.indonesian: "id-id",
    Locale.italian: "it-it",
    Locale.japanese: "ja-jp",
    Locale.korean: "ko-kr",
    Locale.brazil_portuguese: "pt-pt",
    Locale.thai: "th-th",
    Locale.vietnamese: "vi-vn",
    Locale.turkish: "tr-tr",
}


class GenshinClient(genshin.Client):
    def __init__(
        self,
        cookies: str,
        *,
        uid: Optional[int] = None,
        game: genshin.Game = genshin.Game.GENSHIN,
    ) -> None:
        super().__init__(cookies, game=game, uid=uid)

    def set_lang(self, locale: Locale) -> None:
        self.lang = LOCALE_CONVERTER[locale]

    def get_daily_reward_embed(
        self,
        daily_reward: genshin.models.DailyReward,
        game: genshin.Game,
        locale: Locale,
        translator: Translator,
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            locale,
            translator,
            title=_T("Reward claimed", key="reward_claimed_title"),
            description=_T(
                f"{daily_reward.name} x{daily_reward.amount}", translate=False
            ),
        )
        embed.set_thumbnail(url=daily_reward.icon)
        embed.set_author(
            name=_T(game.value, warn_no_key=False), icon_url=GAME_THUMBNAILS[game]
        )
        return embed
