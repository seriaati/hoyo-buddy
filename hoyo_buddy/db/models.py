from enum import StrEnum
from typing import Any, Dict, Optional

import genshin
from discord import Locale
from tortoise import fields
from tortoise.models import Model


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"


GAME_CONVERTER = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
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
    accounts: fields.ManyToManyRelation["HoyoAccount"] = fields.ManyToManyField(
        "models.HoyoAccount", related_name="users"
    )
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: Dict[str, Any] = fields.JSONField(default=dict)  # type: ignore


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: Optional[str] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    users: fields.ManyToManyRelation[User]

    class Meta:
        unique_together = ("uid", "game")
        ordering = ["uid"]

    def __str__(self) -> str:
        return f"[{self.uid}] {self.username}"

    @property
    def client(self) -> GenshinClient:
        return GenshinClient(self.cookies, game=GAME_CONVERTER[self.game], uid=self.uid)


class Settings(Model):
    lang: Optional[str] = fields.CharField(max_length=5, null=True)  # type: ignore
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings"
    )

    @property
    def locale(self) -> Optional[Locale]:
        return Locale(self.lang) if self.lang else None
