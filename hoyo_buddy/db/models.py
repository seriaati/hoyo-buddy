from typing import Any, Dict, Optional

import genshin
from discord import Locale
from tortoise import fields
from tortoise.models import Model

from ..db import GAME_CONVERTER
from ..hoyo.client import GenshinClient
from . import Game

__all__ = (
    "User",
    "HoyoAccount",
    "AccountNotifSettings",
    "Settings",
)


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: Dict[str, Any] = fields.JSONField(default=dict)  # type: ignore
    accounts: fields.ReverseRelation["HoyoAccount"]


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: fields.Field[Optional[str]] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )
    daily_checkin = fields.BooleanField(default=True)

    class Meta:
        unique_together = ("uid", "game", "user")
        ordering = ["uid"]

    def __str__(self) -> str:
        if self.nickname:
            return f"{self.nickname} ({self.uid})"
        return f"{self.username} ({self.uid})"

    @property
    def client(self) -> GenshinClient:
        game: genshin.Game = GAME_CONVERTER[self.game]  # type: ignore
        return GenshinClient(self.cookies, game=game, uid=self.uid)

    def get_game_name(self, locale: Locale, translator: Translator) -> str:
        return translator.translate(_T(self.game.value, warn_no_key=False), locale)


class Settings(Model):
    lang: fields.Field[Optional[str]] = fields.CharField(max_length=5, null=True)  # type: ignore
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings"
    )

    @property
    def locale(self) -> Optional[Locale]:
        return Locale(self.lang) if self.lang else None
