from enum import StrEnum
from typing import Any, Dict, Optional

import genshin
from discord import Locale
from tortoise import fields
from tortoise.models import Model

from ..bot.translator import Translator


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"


GAME_CONVERTER = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
    genshin.Game.GENSHIN: Game.GENSHIN,
    genshin.Game.STARRAIL: Game.STARRAIL,
    genshin.Game.HONKAI: Game.HONKAI,
}

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


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: Dict[str, Any] = fields.JSONField(default=dict)  # type: ignore
    accounts: fields.ReverseRelation["HoyoAccount"]


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: Optional[str] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )

    class Meta:
        unique_together = ("uid", "game")
        ordering = ["uid"]

    def __str__(self) -> str:
        if self.nickname:
            return f"{self.nickname} ({self.uid})"
        return f"{self.username} ({self.uid})"

    @property
    def client(self) -> GenshinClient:
        return GenshinClient(self.cookies, game=GAME_CONVERTER[self.game], uid=self.uid)

    def get_game_name(self, locale: Locale, translator: Translator) -> str:
        return translator.translate(self.game.value, locale)


class Settings(Model):
    lang: Optional[str] = fields.CharField(max_length=5, null=True)  # type: ignore
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings"
    )

    @property
    def locale(self) -> Optional[Locale]:
        return Locale(self.lang) if self.lang else None
