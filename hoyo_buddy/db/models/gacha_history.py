# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.exceptions import IntegrityError

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
    banner_id: fields.Field[int | None] = fields.IntField(null=True)
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
        banner_id: int | None,
        account: HoyoAccount,
    ) -> bool:
        """Create a new GachaHistory record.

        Returns True if the record was created, False if it already exists.

        Args:
            wish_id: Unique identifier for the wish.
            rarity: Rarity of the item.
            time: Timestamp of the wish.
            item_id: Identifier for the item.
            banner_type: Type of the banner.
            banner_id: Identifier for the banner, if applicable. Most wish services do not have this.
            account: The HoyoAccount associated with this wish.
        """
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
                banner_id=banner_id,
            )
        except IntegrityError:
            return False
        return True
