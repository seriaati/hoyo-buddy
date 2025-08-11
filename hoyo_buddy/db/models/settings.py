# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from hoyo_buddy.enums import Locale

from .base import CachedModel

if TYPE_CHECKING:
    from .user import User


class Settings(CachedModel):
    _cache_ttl = 60 * 60 * 24
    _cache_prefix = "settings"

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

    @classmethod
    async def get(cls, user_id: int) -> Settings:
        return await cls.get_cached(user_id)

    @classmethod
    async def get_or_none(cls, user_id: int) -> Settings | None:
        return await cls.get_or_none_cached(user_id)
