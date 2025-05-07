# pyright: reportAssignmentType=false

from __future__ import annotations

import contextlib
import datetime
import pickle
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast

import genshin
import orjson
from discord import Locale
from loguru import logger
from seria.tortoise.model import Model
from tortoise import exceptions, fields

from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed

from ..constants import (
    AUTO_TASK_TOGGLE_FIELDS,
    HB_GAME_TO_GPY_GAME,
    NOTIF_SETTING_FIELDS,
    REGION_TO_PLATFORM,
    SERVER_RESET_HOURS,
    UTC_8,
)
from ..enums import ChallengeType, Game, LeaderboardType, NotesNotifyType, Platform
from ..icons import get_game_icon
from ..utils import blur_uid, get_now

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp

    from ..hoyo.clients.gpy import GenshinClient
    from ..types import AutoTaskType, Challenge, ChallengeWithLang

__all__ = (
    "AccountNotifSettings",
    "CardSettings",
    "ChallengeHistory",
    "CustomImage",
    "FarmNotify",
    "GachaHistory",
    "GachaStats",
    "HoyoAccount",
    "JSONFile",
    "Leaderboard",
    "NotesNotify",
    "Settings",
    "User",
)


class BaseModel(Model):
    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{field}={getattr(self, field)!r}' for field in self._meta.db_fields if hasattr(self, field))})"

    class Meta:
        abstract = True


class User(BaseModel):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation[Settings]
    temp_data: fields.Field[dict[str, Any]] = fields.JSONField(default=dict)
    last_interaction: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    dismissibles: fields.Field[list[str]] = fields.JSONField(default=[])
    accounts: fields.ReverseRelation[HoyoAccount]

    async def set_acc_as_current(self, acc: HoyoAccount) -> None:
        """Set the given account as the current account.

        Args:
            acc: The account to set as current.
        """
        await HoyoAccount.filter(user=self).update(current=False)
        await HoyoAccount.filter(id=acc.id).update(current=True)


class HoyoAccount(BaseModel):
    # Account info
    id = fields.IntField(pk=True, generated=True)
    uid = fields.BigIntField(index=True)
    username = fields.CharField(max_length=32)
    game = fields.CharEnumField(Game, max_length=32)
    cookies = fields.TextField()
    server = fields.CharField(max_length=32)
    device_id: fields.Field[str | None] = fields.CharField(max_length=36, null=True)
    device_fp: fields.Field[str | None] = fields.CharField(max_length=13, null=True)
    region = fields.CharEnumField(genshin.Region, max_length=2)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="accounts"
    )

    # Configurable
    nickname: fields.Field[str | None] = fields.CharField(max_length=32, null=True)
    public = fields.BooleanField(default=True)
    """Whether this account can be seen by others."""
    notif_settings: fields.BackwardOneToOneRelation[AccountNotifSettings]

    # Auto tasks
    # Future me: Make sure to change AUTO_TASK_TOGGLE_FIELDS in constants.py if you modify this section
    daily_checkin = fields.BooleanField(default=True)
    auto_redeem = fields.BooleanField(default=True)
    mimo_auto_task = fields.BooleanField(default=True)
    mimo_auto_buy = fields.BooleanField(default=False)
    mimo_auto_draw = fields.BooleanField(default=False)
    notifs: fields.ReverseRelation[NotesNotify]
    farm_notifs: fields.BackwardOneToOneRelation[FarmNotify]

    # Last completed time for each auto task
    # Future me: Make sure to change AUTO_TASK_LAST_TIME_FIELDS in constants.py if you modify this section
    last_checkin_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_mimo_task_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_mimo_buy_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_mimo_draw_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_redeem_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)

    # Misc
    current = fields.BooleanField(default=False)
    redeemed_codes: fields.Field[list[str]] = fields.JSONField(default=[])
    mimo_all_claimed_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)

    class Meta:
        unique_together = ("uid", "game", "user")
        ordering = ("uid",)

    def __str__(self) -> str:
        return f"{self.nickname or self.username} ({self.uid})"

    @cached_property
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

    @cached_property
    def game_icon(self) -> str:
        return get_game_icon(self.game)

    @property
    def platform(self) -> Platform:
        # 歷史遺留, region 原本可能是 None
        return REGION_TO_PLATFORM[self.region]

    @cached_property
    def dict_cookies(self) -> dict[str, str]:
        return genshin.parse_cookie(self.cookies)

    @cached_property
    def can_redeem_code(self) -> bool:
        return ("cookie_token_v2" in self.dict_cookies) or (
            "ltmid_v2" in self.dict_cookies and "stoken" in self.dict_cookies
        )


class AccountNotifSettings(BaseModel):
    # Future me: Make sure to change NOTIF_SETTING_FIELDS in constants.py if you modify this section
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    mimo_task_success = fields.BooleanField(default=True)
    mimo_task_failure = fields.BooleanField(default=True)
    mimo_buy_success = fields.BooleanField(default=True)
    mimo_buy_failure = fields.BooleanField(default=True)
    mimo_draw_success = fields.BooleanField(default=True)
    mimo_draw_failure = fields.BooleanField(default=True)
    redeem_success = fields.BooleanField(default=True)
    redeem_failure = fields.BooleanField(default=True)

    web_events = fields.BooleanField(default=False)

    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings", pk=True
    )


class Settings(BaseModel):
    lang: fields.Field[str | None] = fields.CharField(max_length=10, null=True)
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
    current_team_image: fields.Field[str | None] = fields.TextField(null=True)
    template = fields.CharField(max_length=32, default="hb1")
    show_rank = fields.BooleanField(default=True)
    """Whether to show the akasha rank of the character, only applies to genshin."""
    show_substat_rolls = fields.BooleanField(default=True)
    highlight_special_stats = fields.BooleanField(default=True)
    highlight_substats: fields.Field[list[int]] = fields.JSONField(default=[])
    use_m3_art = fields.BooleanField(default=False)
    """Whether to use Mindscape 3 art for the ZZZ card."""
    game: fields.Field[Game | None] = fields.CharEnumField(Game, max_length=32, null=True)

    class Meta:
        unique_together = ("character_id", "user", "game")
        ordering = ("character_id",)


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

    hours_before: fields.Field[int | None] = fields.SmallIntField(null=True)
    """Notify X hours before the event. For plannar fissure."""

    class Meta:
        unique_together = ("type", "account")
        ordering = ("type",)


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
    async def read(filename: str, *, default: Any = None, int_key: bool = False) -> Any:
        """Read a JSON file."""
        json_file = await JSONFile.get_or_none(name=filename)
        if json_file is None:
            if default is not None:
                return default
            return {}

        if int_key:
            return {int(key): value for key, value in json_file.data.items()}
        return json_file.data

    @staticmethod
    async def write(filename: str, data: Any, *, auto_str_key: bool = True) -> None:
        """Write a JSON file."""
        if auto_str_key:
            data = {str(key): value for key, value in data.items()}

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
    data: fields.Field[bytes | None] = fields.BinaryField(null=True)
    start_time = fields.DatetimeField()
    end_time = fields.DatetimeField()
    lang: fields.Field[str | None] = fields.CharField(max_length=5, null=True)
    json_data: fields.Field[dict[str, Any] | None] = fields.JSONField(null=True)

    class Meta:
        unique_together = ("uid", "season_id", "challenge_type")
        ordering = ("-end_time",)

    @property
    def duration_str(self) -> str:
        start_time = self.start_time.astimezone(UTC_8)
        end_time = self.end_time.astimezone(UTC_8)
        return f"{start_time:%Y-%m-%d} ~ {end_time:%Y-%m-%d}"

    @property
    def parsed_data(self) -> ChallengeWithLang:
        """Parsed challenge data from binary pickled data."""
        if self.json_data is None:
            if self.data is None:
                # This shouldn't happen, data could be None because of migration to use json_data
                msg = "Both json_data and data are None in ChallengeHistory"
                raise ValueError(msg)
            challenge = pickle.loads(self.data)
        else:
            challenge = self.load_data(self.json_data, challenge_type=self.challenge_type)

        lang = getattr(challenge, "lang", None)
        if lang is None:
            # NOTE: Backward compatibility, old data has lang attr, new data doesn't
            challenge.__dict__["lang"] = self.lang
        return cast("ChallengeWithLang", challenge)

    @classmethod
    def load_data(cls, raw: Mapping[str, Any], *, challenge_type: ChallengeType) -> Challenge:
        if challenge_type is ChallengeType.SPIRAL_ABYSS:
            return genshin.models.SpiralAbyss(**raw)
        if challenge_type is ChallengeType.IMG_THEATER:
            return genshin.models.ImgTheaterData(**raw)
        if challenge_type is ChallengeType.SHIYU_DEFENSE:
            return genshin.models.ShiyuDefense(**raw)
        if challenge_type is ChallengeType.ASSAULT:
            return genshin.models.DeadlyAssault(**raw)
        if challenge_type is ChallengeType.APC_SHADOW:
            return genshin.models.StarRailAPCShadow(**raw)
        if challenge_type is ChallengeType.MOC:
            return genshin.models.StarRailChallenge(**raw)
        if challenge_type is ChallengeType.PURE_FICTION:
            return genshin.models.StarRailPureFiction(**raw)

    @classmethod
    async def add_data(
        cls,
        *,
        uid: int,
        challenge_type: ChallengeType,
        season_id: int,
        raw: Mapping[str, Any],
        lang: str,
    ) -> None:
        data = cls.load_data(raw, challenge_type=challenge_type)

        if isinstance(data, genshin.models.SpiralAbyss | genshin.models.DeadlyAssault):
            start_time = data.start_time
            end_time = data.end_time
            name = None
        elif isinstance(data, genshin.models.ImgTheaterData):
            start_time = data.schedule.start_datetime
            end_time = data.schedule.end_datetime
            name = None
        elif isinstance(data, genshin.models.ShiyuDefense):
            start_time = data.begin_time
            end_time = data.end_time
            name = None
        else:
            season = next((season for season in data.seasons if season.id == season_id), None)
            if season is None:
                logger.error(f"Cannot find season with id {season_id} in add_data")
                return
            start_time = season.begin_time.datetime
            end_time = season.end_time.datetime
            name = season.name

        try:
            await cls.create(
                uid=uid,
                season_id=season_id,
                challenge_type=challenge_type,
                start_time=start_time,
                end_time=end_time,
                name=name,
                lang=lang,
                json_data=raw,
            )
        except exceptions.IntegrityError:
            await cls.filter(uid=uid, season_id=season_id, challenge_type=challenge_type).update(
                name=name, lang=lang, json_data=raw
            )


class GachaHistory(BaseModel):
    id = fields.IntField(pk=True, generated=True)

    wish_id = fields.BigIntField()
    rarity = fields.IntField()
    time = fields.DatetimeField()
    item_id = fields.IntField()
    banner_type = fields.IntField()
    num = fields.IntField()
    num_since_last = fields.IntField()
    """Number of pulls since the last 5 or 4 star pull."""

    game = fields.CharEnumField(Game, max_length=32)
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="wishes", index=True
    )
    account_id: fields.Field[int]

    class Meta:
        unique_together = ("wish_id", "game", "account")
        ordering = ("-wish_id",)

    @classmethod
    async def create(
        cls,
        *,
        wish_id: int,
        rarity: int,
        time: datetime.datetime,
        item_id: int,
        banner_type: int,
        account: HoyoAccount,
    ) -> bool:
        try:
            await super().create(
                wish_id=wish_id,
                rarity=rarity,
                time=time,
                item_id=item_id,
                banner_type=banner_type,
                num=1,
                num_since_last=1,
                game=account.game,
                account=account,
                account_id=account.id,
            )
        except exceptions.IntegrityError:
            return False
        return True


class GachaStats(BaseModel):
    account_id = fields.IntField()
    lifetime_pulls = fields.IntField()
    avg_5star_pulls = fields.FloatField()
    avg_4star_pulls = fields.FloatField()
    win_rate = fields.FloatField()
    """50/50 win rate, before multiplying 100."""
    game = fields.CharEnumField(Game, max_length=32)
    banner_type = fields.IntField()

    class Meta:
        unique_together = ("account_id", "banner_type", "game")

    @classmethod
    async def create_or_update(
        cls,
        *,
        account: HoyoAccount,
        lifetime_pulls: int,
        avg_5star_pulls: float,
        avg_4star_pulls: float,
        win_rate: float,
        banner_type: int,
    ) -> None:
        try:
            await super().create(
                account_id=account.id,
                lifetime_pulls=lifetime_pulls,
                avg_5star_pulls=avg_5star_pulls,
                avg_4star_pulls=avg_4star_pulls,
                win_rate=win_rate,
                game=account.game,
                banner_type=banner_type,
            )
        except exceptions.IntegrityError:
            await cls.filter(account_id=account.id, banner_type=banner_type).update(
                lifetime_pulls=lifetime_pulls,
                avg_5star_pulls=avg_5star_pulls,
                avg_4star_pulls=avg_4star_pulls,
                win_rate=win_rate,
            )


class Leaderboard(BaseModel):
    type = fields.CharEnumField(LeaderboardType, max_length=32)
    game = fields.CharEnumField(Game, max_length=32)
    value = fields.FloatField()
    uid = fields.BigIntField()
    rank = fields.IntField()
    username = fields.CharField(max_length=32)
    extra_info: fields.Field[dict[str, Any]] = fields.JSONField(default={}, null=True)

    class Meta:
        unique_together = ("type", "game", "uid")

    @classmethod
    async def update_or_create(
        cls,
        *,
        type_: LeaderboardType,
        game: Game,
        uid: int,
        value: float,
        username: str,
        extra_info: dict[str, Any] | None,
    ) -> None:
        extra_info = extra_info or {}

        try:
            await cls.create(
                type=type_,
                game=game,
                uid=uid,
                value=value,
                username=username,
                rank=0,
                extra_info=extra_info,
            )
        except exceptions.IntegrityError:
            lb = await cls.get(type=type_, game=game, uid=uid)
            if lb.value < value:
                await cls.filter(type=type_, game=game, uid=uid).update(
                    value=value, username=username, extra_info=extra_info
                )


class CustomImage(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    name: fields.Field[str | None] = fields.CharField(max_length=100, null=True)
    url = fields.TextField(null=True)

    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="custom_images"
    )

    class Meta:
        unique_together = ("character_id", "user", "url")
        ordering = ("character_id", "id")

    @classmethod
    async def create(
        cls, *, url: str, character_id: str, user_id: int, name: str | None = None
    ) -> None:
        with contextlib.suppress(exceptions.IntegrityError):
            await super().create(url=url, character_id=character_id, user_id=user_id, name=name)


class DiscordEmbed(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    data: fields.Field[dict[str, Any]] = fields.JSONField()
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="embeds"
    )
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="embeds"
    )
    task_type: AutoTaskType = fields.CharField(max_length=20)
    type: Literal["default", "error"] = fields.CharField(max_length=7)

    user_id: int
    account_id: int

    @classmethod
    async def create(
        cls,
        embed: DefaultEmbed | ErrorEmbed,
        *,
        user_id: int,
        account_id: int,
        task_type: AutoTaskType,
    ) -> None:
        notif_fields = NOTIF_SETTING_FIELDS.get(task_type, ())
        toggle_field = AUTO_TASK_TOGGLE_FIELDS.get(task_type)

        if isinstance(embed, ErrorEmbed) and toggle_field is not None:
            await HoyoAccount.filter(id=account_id).update(**{toggle_field: False})

        if isinstance(embed, DefaultEmbed) and notif_fields:
            success_field = notif_fields[0]
            notif_settings = await AccountNotifSettings.get_or_none(account_id=account_id).only(
                success_field
            )
            if not getattr(notif_settings, success_field):
                return
        elif isinstance(embed, ErrorEmbed) and notif_fields:
            failure_field = notif_fields[1]
            notif_settings = await AccountNotifSettings.get_or_none(account_id=account_id).only(
                failure_field
            )
            if not getattr(notif_settings, failure_field):
                return

        await super().create(
            data=embed.to_dict(),
            user_id=user_id,
            account_id=account_id,
            task_type=task_type,
            type="default" if isinstance(embed, DefaultEmbed) else "error",
        )


class DMChannel(BaseModel):
    id = fields.BigIntField(pk=True, generated=False)
    user_id = fields.BigIntField()
