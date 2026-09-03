# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Self

from tortoise import fields

from hoyo_buddy.enums import Game

from .base import BaseModel

if TYPE_CHECKING:
    from .hoyo_account import HoyoAccount


class GachaHistory(BaseModel):
    id = fields.IntField(pk=True, generated=True)

    wish_id = fields.BigIntField()
    rarity = fields.IntField()
    """Canonical rarity: 5 = 5-star / S, 4 = 4-star / A, 3 = 3-star / B, regardless of game.

    Importers convert from each source's own scale before constructing records.
    """
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
        unique_together = ("wish_id", "game", "account", "banner_type")
        ordering = ("-wish_id",)

    @classmethod
    async def get_wish_count(cls, account: HoyoAccount) -> int:
        return await cls.filter(account=account).count()

    @classmethod
    async def bulk_create(cls, records: list[Self], **kwargs) -> None:
        invalid = {record.rarity for record in records} - {3, 4, 5}
        if invalid:
            msg = f"Non-canonical rarities {sorted(invalid)}, expected 3, 4, or 5"
            raise ValueError(msg)

        return await super().bulk_create(records, batch_size=5000, ignore_conflicts=True, **kwargs)
