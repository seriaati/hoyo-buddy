# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from .base import BaseModel
from .hoyo_account import HoyoAccount

if TYPE_CHECKING:
    import datetime

    from .settings import Settings


class User(BaseModel):
    id = fields.BigIntField(pk=True, index=True, generated=False)
    settings: fields.BackwardOneToOneRelation[Settings]
    temp_data: fields.Field[dict[str, Any]] = fields.JSONField(default=dict)
    last_interaction: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    dismissibles: fields.Field[list[str]] = fields.JSONField(default=["m3_art", "hsr_temp2"])
    accounts: fields.ReverseRelation[HoyoAccount]
    ai_image_count = fields.SmallIntField(default=0)
    ai_image_date: fields.Field[datetime.date | None] = fields.DateField(null=True)

    async def set_acc_as_current(self, acc: HoyoAccount) -> None:
        """Set the given account as the current account.

        Args:
            acc: The account to set as current.
        """
        await HoyoAccount.filter(user=self).update(current=False)
        await HoyoAccount.filter(id=acc.id).update(current=True)
