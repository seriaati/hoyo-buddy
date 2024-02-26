from typing import TYPE_CHECKING, Any

from discord import Locale
from seria.tortoise.model import Model
from tortoise import fields

from ..hoyo.client import GenshinClient
from .enums import GAME_CONVERTER, Game

if TYPE_CHECKING:
    import genshin

__all__ = (
    "User",
    "HoyoAccount",
    "AccountNotifSettings",
    "Settings",
)


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)  # noqa: A003
    settings: fields.BackwardOneToOneRelation["Settings"]
    temp_data: dict[str, Any] = fields.JSONField(default=dict)  # type: ignore
    accounts: fields.ReverseRelation["HoyoAccount"]

    def __str__(self) -> str:
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
        "models.HoyoAccount", related_name="notif_settings", pk=True
    )


class Settings(Model):
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)  # type: ignore
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings", pk=True
    )

    @property
    def locale(self) -> Locale | None:
        return Locale(self.lang) if self.lang else None


class CardSettings(Model):
    character_id = fields.CharField(max_length=8)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="card_settings"
    )
    dark_mode = fields.BooleanField()
    custom_images: list[str] = fields.JSONField(default=[])  # type: ignore
    """URLs of custom images."""
    custom_primary_color: str | None = fields.CharField(max_length=7, null=True)  # type: ignore

    class Meta:
        unique_together = ("character_id", "user")
        ordering = ["character_id"]
