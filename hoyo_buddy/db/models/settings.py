# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tortoise import fields

from hoyo_buddy.enums import Locale

from .base import CachedModel

if TYPE_CHECKING:
    from .user import User


class Settings(CachedModel):
    _cache_ttl = 60 * 60 * 24
    _pks = ("user_id",)

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
    async def get(cls, *, user_id: int | None = None) -> Self:
        return await super().get(user_id=user_id)

    @classmethod
    async def get_or_none(cls, *, user_id: int) -> Self | None:
        return await super().get_or_none(user_id=user_id)
