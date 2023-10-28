from typing import Optional

import genshin
from discord import Locale

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
