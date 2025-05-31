# pyright: reportAssignmentType=false
from __future__ import annotations

import datetime
from functools import cached_property
from typing import TYPE_CHECKING

import genshin
from tortoise import fields

from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME, REGION_TO_PLATFORM, SERVER_RESET_HOURS
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.utils import blur_uid, get_now

from .base import BaseModel

if TYPE_CHECKING:
    from hoyo_buddy.hoyo.clients.gpy import GenshinClient

    from .farm_notify import FarmNotify
    from .notes_notify import NotesNotify
    from .notif_settings import AccountNotifSettings
    from .user import User


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
        from hoyo_buddy.hoyo.clients.gpy import GenshinClient  # noqa: PLC0415

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
