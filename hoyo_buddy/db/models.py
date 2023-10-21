from enum import StrEnum
from typing import Optional

from tortoise import fields
from tortoise.models import Model


class Game(StrEnum):
    GENSHIN = "genshin"  # Genshin Impact
    STARRAIL = "starrail"  # Honkai: Star Rail
    HONKAI = "honkai"  # Honkai Impact 3rd
    ZZZ = "zzz"  # Zenless Zone Zero


class User(Model):
    id = fields.BigIntField(pk=True, index=True)
    accounts = fields.ManyToManyField("models.HoyoAccount", related_name="users")
    settings: fields.OneToOneRelation["Settings"] = fields.OneToOneField(
        "models.Settings", related_name="user"
    )


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: Optional[str] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game)
    cookie = fields.JSONField()
    users: fields.ManyToManyRelation[User]

    class Meta:
        unique_together = ("uid", "game")


class Settings(Model):
    lang: Optional[str] = fields.CharField(max_length=5, null=True)  # type: ignore
    user: fields.BackwardOneToOneRelation[User]
