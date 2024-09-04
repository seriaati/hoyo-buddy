# pyright: reportAssignmentType=false

from __future__ import annotations

import datetime
import pickle
from functools import cached_property
from typing import TYPE_CHECKING, Any

import genshin
import orjson
from discord import Locale
from loguru import logger
from seria.tortoise.model import Model
from tortoise import exceptions, fields

from ..constants import HB_GAME_TO_GPY_GAME, SERVER_RESET_HOURS, UTC_8
from ..enums import ChallengeType, Game, NotesNotifyType, Platform
from ..icons import get_game_icon
from ..utils import blur_uid, get_now

if TYPE_CHECKING:
    import aiohttp

    from hoyo_buddy.types import ChallengeWithLang

    from ..hoyo.clients.gpy import GenshinClient
    from ..types import Challenge, Interaction


class BaseModel(Model):
    def __str__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{field}={getattr(self, field)!r}' for field in self._meta.db_fields)})"

    def __repr__(self) -> str:
        return str(self)

    class Meta:
        abstract = True


class User(BaseModel):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation[Settings]
    temp_data: fields.Field[dict[str, Any]] = fields.JSONField(default=dict)
    last_interaction: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    accounts: fields.ReverseRelation[HoyoAccount]

    async def set_acc_as_current(self, acc: HoyoAccount) -> None:
        """Set the given account as the current account.

        Args:
            acc: The account to set as current.
        """
        await HoyoAccount.filter(user=self).update(current=False)
        acc.current = True
        await acc.save(update_fields=("current",))


class HoyoAccount(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    uid = fields.BigIntField(index=True)
    username = fields.CharField(max_length=32)
    nickname: fields.Field[str | None] = fields.CharField(max_length=32, null=True)
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
    redeemed_codes: fields.Field[list[str]] = fields.JSONField(default=[])
    auto_redeem = fields.BooleanField(default=True)
    public = fields.BooleanField(default=True)
    """Whether this account can be seen by others."""
    device_id: fields.Field[str | None] = fields.CharField(max_length=36, null=True)
    device_fp: fields.Field[str | None] = fields.CharField(max_length=13, null=True)
    region: genshin.Region | None = fields.CharEnumField(genshin.Region, max_length=2, null=True)

    class Meta:
        unique_together = ("uid", "game", "user")
        ordering = ["uid"]

    @property
    def blurred_display(self) -> str:
        return f"{self.nickname or self.username} ({blur_uid(self.uid)})"

    @cached_property
    def client(self) -> GenshinClient:
        from ..hoyo.clients.gpy import GenshinClient  # noqa: PLC0415

        return GenshinClient(self)

    @property
    def server_reset_datetime(self) -> datetime.datetime:
        """Server reset time in UTC+8."""
        server = genshin.utility.recognize_server(self.uid, HB_GAME_TO_GPY_GAME[self.game])
        reset_hour = SERVER_RESET_HOURS.get(server, 4)
        reset_time = get_now().replace(hour=reset_hour, minute=0, second=0, microsecond=0)
        if reset_time < get_now():
            reset_time += datetime.timedelta(days=1)
        return reset_time

    @property
    def game_icon(self) -> str:
        return get_game_icon(self.game)

    @property
    def platform(self) -> Platform:
        region = self.region or genshin.utility.recognize_region(
            self.uid, HB_GAME_TO_GPY_GAME[self.game]
        )
        if region is None:
            return Platform.HOYOLAB
        return Platform.HOYOLAB if region is genshin.Region.OVERSEAS else Platform.MIYOUSHE


class AccountNotifSettings(BaseModel):
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings", pk=True
    )


class Settings(BaseModel):
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)
    dark_mode = fields.BooleanField(default=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", related_name="settings", pk=True
    )
    gi_card_temp = fields.CharField(max_length=32, default="hb1")
    hsr_card_temp = fields.CharField(max_length=32, default="hb1")
    zzz_card_temp = fields.CharField(max_length=32, default="hb2")
    team_card_dark_mode = fields.BooleanField(default=False)
    enable_dyk = fields.BooleanField(default=True)

    @property
    def locale(self) -> Locale | None:
        return Locale(self.lang) if self.lang else None


class CardSettings(BaseModel):
    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="card_settings"
    )
    dark_mode = fields.BooleanField()
    custom_images: fields.Field[list[str]] = fields.JSONField(default=[])
    """URLs of custom images."""
    custom_primary_color: fields.Field[str | None] = fields.CharField(max_length=7, null=True)
    current_image: fields.Field[str | None] = fields.TextField(null=True)
    template = fields.CharField(max_length=32, default="hb1")
    show_rank = fields.BooleanField(default=True)
    """Whether to show the akasha rank of the character, only applies to genshin."""

    class Meta:
        unique_together = ("character_id", "user")
        ordering = ["character_id"]


class EnkaCache(BaseModel):
    uid = fields.BigIntField(pk=True, index=True)
    hsr: fields.Field[dict[str, Any]] = fields.JSONField(default={})
    genshin: fields.Field[dict[str, Any]] = fields.JSONField(default={})
    hoyolab: fields.Field[dict[str, Any]] = fields.JSONField(default={})
    hoyolab_zzz: fields.Field[dict[str, Any] | None] = fields.JSONField(default={}, null=True)
    extras: fields.Field[dict[str, dict[str, Any]]] = fields.JSONField(default={})

    class Meta:
        ordering = ["uid"]


class NotesNotify(BaseModel):
    type = fields.IntEnumField(NotesNotifyType)
    enabled = fields.BooleanField(default=True)
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="notifs"
    )

    last_notif_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_check_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    est_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    """Estimated time for the threshold to be reached."""

    notify_interval = fields.SmallIntField()
    """Notify interval in minutes."""
    check_interval = fields.SmallIntField()
    """Check interval in minutes."""

    max_notif_count = fields.SmallIntField(default=5)
    current_notif_count = fields.SmallIntField(default=0)

    threshold: fields.Field[int | None] = fields.SmallIntField(null=True)
    """For resin, realm currency, trailblaze power, and reservered trailblaze power."""
    notify_time: fields.Field[int | None] = fields.SmallIntField(null=True)
    """X hour before server resets. For dailies, resin discount, and echo of war."""
    notify_weekday: fields.Field[int | None] = fields.SmallIntField(null=True)
    """For resin discount and echo of war, 1~7, 1 is Monday."""

    class Meta:
        unique_together = ("type", "account")
        ordering = ["type"]


class FarmNotify(BaseModel):
    enabled = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="farm_notifs", pk=True
    )
    item_ids: fields.Field[list[str]] = fields.JSONField(default=[])


class JSONFile(BaseModel):
    name = fields.CharField(max_length=100, index=True)
    data: fields.Field[Any] = fields.JSONField()

    @staticmethod
    async def read(filename: str) -> Any:
        """Read a JSON file."""
        json_file = await JSONFile.get_or_none(name=filename)
        if json_file is None:
            return {}

        return json_file.data

    @staticmethod
    async def write(filename: str, data: Any) -> None:
        """Write a JSON file."""
        json_file = await JSONFile.get_or_none(name=filename)
        if json_file is None:
            await JSONFile.create(name=filename, data=data)
            return

        json_file.data = data
        await json_file.save(update_fields=("data",))

    @staticmethod
    async def fetch_and_cache(session: aiohttp.ClientSession, *, url: str, filename: str) -> Any:
        async with session.get(url) as resp:
            data = orjson.loads(await resp.text())
            await JSONFile.write(filename, data)
            return data


class ChallengeHistory(BaseModel):
    uid = fields.BigIntField(index=True)
    season_id = fields.IntField()
    name: fields.Field[str | None] = fields.CharField(max_length=64, null=True)
    challenge_type = fields.CharEnumField(ChallengeType, max_length=32)
    data = fields.BinaryField()
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    lang = fields.CharField(max_length=5, null=True)

    class Meta:
        unique_together = ("uid", "season_id", "challenge_type")
        ordering = ["-end_time"]

    @property
    def duration_str(self) -> str:
        start_time = self.start_time.astimezone(UTC_8)
        end_time = self.end_time.astimezone(UTC_8)
        return f"{start_time:%Y-%m-%d} ~ {end_time:%Y-%m-%d}"

    @property
    def parsed_data(self) -> ChallengeWithLang:
        """Parsed challenge data from binary pickled data."""
        challenge = pickle.loads(self.data)
        lang = getattr(challenge, "lang", None)
        if lang is None:
            # NOTE: Backward compatibility, old data has lang attr, new data doesn't
            logger.debug("No lang found in challenge data")
            challenge.__dict__["lang"] = self.lang
        return challenge

    @classmethod
    async def add_data(
        cls, *, uid: int, challenge_type: ChallengeType, season_id: int, data: Challenge, lang: str
    ) -> None:
        if isinstance(data, genshin.models.SpiralAbyss):
            start_time = data.start_time
            end_time = data.end_time
            name = None
        elif isinstance(data, genshin.models.ImgTheaterData):
            start_time = data.schedule.start_time
            end_time = data.schedule.end_time
            name = None
        else:
            season = next(season for season in data.seasons if season.id == season_id)
            start_time = season.begin_time.datetime
            end_time = season.end_time.datetime
            name = season.name

        try:
            await cls.create(
                uid=uid,
                season_id=season_id,
                challenge_type=challenge_type,
                data=pickle.dumps(data),
                start_time=start_time,
                end_time=end_time,
                name=name,
                lang=lang,
            )
        except exceptions.IntegrityError:
            await cls.filter(uid=uid, season_id=season_id, challenge_type=challenge_type).update(
                data=pickle.dumps(data), name=name, lang=lang
            )


async def get_locale(i: Interaction) -> Locale:
    cache = i.client.cache
    key = f"{i.user.id}:lang"
    if await cache.exists(key):
        locale = await cache.get(key)
        return Locale(locale) if locale is not None else i.locale
    settings = await Settings.get(user_id=i.user.id).only("lang")
    locale = settings.locale or i.locale
    await cache.set(key, locale.value)
    return locale


async def get_enable_dyk(i: Interaction) -> bool:
    cache = i.client.cache
    key = f"{i.user.id}:dyk"
    if await cache.exists(key):
        return await cache.get(key)
    settings = await Settings.get(user_id=i.user.id).only("enable_dyk")
    await cache.set(key, settings.enable_dyk)
    return settings.enable_dyk


async def get_dyk(i: Interaction) -> str:
    enable_dyk = await get_enable_dyk(i)
    locale = await get_locale(i)
    if not enable_dyk:
        return ""
    return i.client.translator.get_dyk(locale)
