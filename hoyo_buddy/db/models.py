from typing import TYPE_CHECKING, Any, Self

from discord import Locale
from tortoise import fields
from tortoise.exceptions import DoesNotExist, IntegrityError
from tortoise.models import Model as TortoiseModel

from ..db import GAME_CONVERTER
from ..hoyo.client import GenshinClient
from . import Game

if TYPE_CHECKING:
    import genshin

__all__ = (
    "User",
    "HoyoAccount",
    "AccountNotifSettings",
    "Settings",
)


class Model(TortoiseModel):
    @classmethod
    async def get_or_create(cls, **kwargs: Any) -> tuple[Self, bool]:
        try:
            return await cls.get(**kwargs), False
        except DoesNotExist:
            return await cls.create(**kwargs), True

    @classmethod
    async def silent_create(cls, **kwargs: Any) -> Self | None:
        try:
            return await cls.create(find_from_cache_first=True, **kwargs)
        except IntegrityError:
            return None


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)  # noqa: A003
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: dict[str, Any] = fields.JSONField()  # type: ignore
    accounts: fields.ReverseRelation["HoyoAccount"]

    @property
    def _key(self) -> str:
        return str(self.id)


class HoyoAccount(Model):
    uid = fields.IntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: fields.Field[str | None] = fields.CharField(max_length=32, null=True)  # type: ignore
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )
    daily_checkin = fields.BooleanField(default=True)
    notif_settings: fields.BackwardOneToOneRelation["AccountNotifSettings"]

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


class AccountNotifSettings(Model):
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings"
    )


class Settings(Model):
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)  # type: ignore
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings"
    )

    @property
    def locale(self) -> Locale | None:
        return Locale(self.lang) if self.lang else None
