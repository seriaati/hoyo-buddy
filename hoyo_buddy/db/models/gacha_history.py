# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import exceptions, fields

from hoyo_buddy.enums import Game

from .base import BaseModel

if TYPE_CHECKING:
    import datetime

    from .hoyo_account import HoyoAccount


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
