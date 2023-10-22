from enum import StrEnum
from typing import Any, Dict, Optional

from tortoise import fields
from tortoise.models import Model


class Game(StrEnum):
    GENSHIN = "genshin"  # Genshin Impact
    STARRAIL = "hkrpg"  # Honkai: Star Rail
    HONKAI = "honkai3rd"  # Honkai Impact 3rd


class User(Model):
    id = fields.BigIntField(pk=True, index=True)
    accounts = fields.ManyToManyField("models.HoyoAccount", related_name="users")
    settings: fields.OneToOneRelation["Settings"] = fields.OneToOneField(
        "models.Settings", related_name="user"
    )
    temp_data: Dict[str, Any] = fields.JSONField()  # type: ignore


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: Optional[str] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game)
    cookies: Dict[str, Any] = fields.JSONField()  # type: ignore
    users: fields.ManyToManyRelation[User]

    class Meta:
        unique_together = ("uid", "game")


class Settings(Model):
    lang: Optional[str] = fields.CharField(max_length=5, null=True)  # type: ignore
    user: fields.BackwardOneToOneRelation[User]
