from enum import StrEnum
from typing import TYPE_CHECKING

import yatta
from discord import Locale
from yatta import Language

from ..embeds import DefaultEmbed

if TYPE_CHECKING:
    from types import TracebackType

    from ..bot.translator import Translator

LOCALE_TO_LANG: dict[Locale, Language] = {
    Locale.taiwan_chinese: Language.CHT,
    Locale.chinese: Language.CN,
    Locale.german: Language.DE,
    Locale.american_english: Language.EN,
    Locale.spain_spanish: Language.ES,
    Locale.french: Language.FR,
    Locale.indonesian: Language.ID,
    Locale.japanese: Language.JP,
    Locale.korean: Language.KR,
    Locale.brazil_portuguese: Language.PT,
    Locale.russian: Language.RU,
    Locale.thai: Language.TH,
    Locale.vietnamese: Language.VI,
}


class ItemCategory(StrEnum):
    CHARACTERS = "Characters"
    LIGHT_CONES = "Light Cones"
    ITEMS = "Items"
    RELICS = "Relics"
    BOOKS = "Books"


class YattaAPIClient(yatta.YattaAPI):
    def __init__(self, locale: Locale, translator: "Translator") -> None:
        super().__init__(LOCALE_TO_LANG.get(locale, Language.EN))
        self.locale = locale
        self.translator = translator

    async def __aenter__(self) -> "YattaAPIClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> None:
        return await super().close()

    def get_character_embed(self, character: yatta.CharacterDetail) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator, title=character.name)
        return embed
