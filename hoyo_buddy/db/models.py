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
}


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    accounts: fields.ManyToManyRelation["HoyoAccount"] = fields.ManyToManyField(
        "models.HoyoAccount", related_name="users"
    )
    settings: fields.OneToOneRelation["Settings"] = fields.OneToOneField(
        "models.Settings", related_name="user"
    )
    temp_data: Dict[str, Any] = fields.JSONField(default=dict)  # type: ignore


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: Optional[str] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game)
    cookies: Dict[str, Any] = fields.JSONField()  # type: ignore
    users: fields.ManyToManyRelation[User]

    class Meta:
        unique_together = ("uid", "game")

    @property
    def client(self) -> genshin.Client:
        return genshin.Client(
            self.cookies, game=GAME_CONVERTER[self.game], uid=self.uid
        )


class Settings(Model):
    lang: Optional[str] = fields.CharField(max_length=5, null=True)  # type: ignore
    user: fields.BackwardOneToOneRelation[User]

    @property
    def locale(self) -> Optional[Locale]:
        return Locale(self.lang) if self.lang else None
