# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from tortoise import fields

from hoyo_buddy.enums import Game

from .base import BaseModel

if TYPE_CHECKING:
    from .hoyo_account import HoyoAccount


class GachaHistory(BaseModel):
    id = fields.IntField(pk=True, generated=True)

    wish_id = fields.BigIntField()
    rarity = fields.IntField()
    time = fields.DatetimeField()
    item_id = fields.IntField()
    banner_type = fields.IntField()
    banner_id: fields.Field[int | None] = fields.IntField(null=True)
    num = fields.IntField(default=1)
    num_since_last = fields.IntField(default=1)
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
    async def get_wish_count(cls, account: HoyoAccount) -> int:
        return await cls.filter(account=account).count()

    @classmethod
    async def bulk_create(cls, records: list[Self], **kwargs: Any) -> None:
        return await super().bulk_create(records, batch_size=5000, ignore_conflicts=True, **kwargs)
