from __future__ import annotations

import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Any

import genshin
from discord import Locale
from seria.tortoise.model import Model
from tortoise import fields

from ..constants import HB_GAME_TO_GPY_GAME, UID_SERVER_RESET_HOURS
from ..enums import Game, NotesNotifyType, Platform
from ..icons import get_game_icon
from ..utils import blur_uid, get_now

if TYPE_CHECKING:
    from ..hoyo.clients.gpy_client import GenshinClient


class User(Model):
    id = fields.BigIntField(pk=True, index=True, generated=False)  # noqa: A003
    settings: fields.BackwardOneToOneRelation[Settings]
    temp_data: fields.Field[dict[str, Any]] = fields.JSONField(default=dict)  # pyright: ignore [reportAssignmentType]
    last_interaction: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)  # pyright: ignore [reportAssignmentType]
    accounts: fields.ReverseRelation[HoyoAccount]

    def __str__(self) -> str:
        return str(self.id)

    async def set_acc_as_current(self, acc: HoyoAccount) -> None:
        """Set the given account as the current account.

        Args:
            acc: The account to set as current.
        """
        await HoyoAccount.filter(user=self).update(current=False)
        acc.current = True
        await acc.save(update_fields=("current",))


class HoyoAccount(Model):
    id = fields.IntField(pk=True, generated=True)
    uid = fields.BigIntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: fields.Field[str | None] = fields.CharField(max_length=32, null=True)  # pyright: ignore [reportAssignmentType]
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )
    daily_checkin = fields.BooleanField(default=True)
    current = fields.BooleanField(default=False)
    notif_settings: fields.BackwardOneToOneRelation[AccountNotifSettings]
    notifs: fields.ReverseRelation[NotesNotify]
    farm_notifs: fields.BackwardOneToOneRelation[FarmNotify]
    redeemed_codes: fields.Field[list[str]] = fields.JSONField(default=[])  # pyright: ignore [reportAssignmentType]
    auto_redeem = fields.BooleanField(default=True)
    public = fields.BooleanField(default=True)
    """Whether this account can be seen by others."""

    class Meta:
        unique_together = ("uid", "game", "user")
        ordering = ["uid"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.nickname or self.username} ({self.uid})"

    @property
    def blurred_display(self) -> str:
        return f"{self.nickname or self.username} ({blur_uid(self.uid)})"

    @cached_property
    def client(self) -> GenshinClient:
        from ..hoyo.clients.gpy_client import GenshinClient  # noqa: PLC0415

        return GenshinClient(self)

    @cached_property
    def server_reset_datetime(self) -> datetime.datetime:
        """Server reset time in UTC+8."""
        for uid_start, reset_hour in UID_SERVER_RESET_HOURS.items():
            if str(self.uid).startswith(uid_start):
                reset_time = get_now().replace(hour=reset_hour, minute=0, second=0, microsecond=0)
                break
        else:
            reset_time = get_now().replace(hour=4, minute=0, second=0, microsecond=0)

        if reset_time < get_now():
            reset_time += datetime.timedelta(days=1)

        return reset_time

    @cached_property
    def game_icon(self) -> str:
        return get_game_icon(self.game)

    @cached_property
    def platform(self) -> Platform:
        region = genshin.utility.recognize_region(self.uid, HB_GAME_TO_GPY_GAME[self.game])
        return Platform.HOYOLAB if region is genshin.Region.OVERSEAS else Platform.MIYOUSHE


class AccountNotifSettings(Model):
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings", pk=True
    )


class Settings(Model):
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)  # pyright: ignore [reportAssignmentType]
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings", pk=True
    )

    @property
    def locale(self) -> Locale | None:
        return Locale(self.lang) if self.lang else None


class CardSettings(Model):
    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="card_settings"
    )
    dark_mode = fields.BooleanField()
    custom_images: fields.Field[list[str]] = fields.JSONField(default=[])  # pyright: ignore [reportAssignmentType]
    """URLs of custom images."""
    custom_primary_color: fields.Field[str | None] = fields.CharField(max_length=7, null=True)  # pyright: ignore [reportAssignmentType]
    current_image: fields.Field[str | None] = fields.CharField(max_length=100, null=True)  # pyright: ignore [reportAssignmentType]
    template = fields.CharField(max_length=32, default="hb1")

    class Meta:
        unique_together = ("character_id", "user")
        ordering = ["character_id"]  # noqa: RUF012


class EnkaCache(Model):
    uid = fields.BigIntField(pk=True, index=True)
    hsr: fields.Field[bytes | None] = fields.BinaryField(null=True)  # pyright: ignore [reportAssignmentType]
    genshin: fields.Field[bytes | None] = fields.BinaryField(null=True)  # pyright: ignore [reportAssignmentType]
    hoyolab: fields.Field[bytes | None] = fields.BinaryField(null=True)  # pyright: ignore [reportAssignmentType]
    extras: fields.Field[dict[str, dict[str, Any]]] = fields.JSONField(default={})  # pyright: ignore [reportAssignmentType]

    class Meta:
        ordering = ["uid"]  # noqa: RUF012


class NotesNotify(Model):
    type = fields.IntEnumField(NotesNotifyType)
    enabled = fields.BooleanField(default=True)
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="notifs"
    )

    last_notif_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)  # pyright: ignore [reportAssignmentType]
    last_check_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)  # pyright: ignore [reportAssignmentType]
    est_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)  # pyright: ignore [reportAssignmentType]
    """Estimated time for the threshold to be reached."""

    notify_interval = fields.SmallIntField()
    """Notify interval in minutes."""
    check_interval = fields.SmallIntField()
    """Check interval in minutes."""

    max_notif_count = fields.SmallIntField(default=5)
    current_notif_count = fields.SmallIntField(default=0)

    threshold: fields.Field[int | None] = fields.SmallIntField(null=True)  # pyright: ignore [reportAssignmentType]
    """For resin, realm currency, trailblaze power, and reservered trailblaze power."""
    notify_time: fields.Field[int | None] = fields.SmallIntField(null=True)  # pyright: ignore [reportAssignmentType]
    """X hour before server resets. For dailies, resin discount, and echo of war."""
    notify_weekday: fields.Field[int | None] = fields.SmallIntField(null=True)  # pyright: ignore [reportAssignmentType]
    """For resin discount and echo of war."""

    class Meta:
        unique_together = ("type", "account")
        ordering = ["type"]  # noqa: RUF012


class FarmNotify(Model):
    enabled = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="farm_notifs", pk=True
    )
    item_ids: fields.Field[list[str]] = fields.JSONField(default=[])  # pyright: ignore [reportAssignmentType]
