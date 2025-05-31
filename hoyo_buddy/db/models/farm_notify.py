# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from .base import BaseModel

if TYPE_CHECKING:
    from .hoyo_account import HoyoAccount


class FarmNotify(BaseModel):
    enabled = fields.BooleanField(default=True)
    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="farm_notifs", pk=True
    )
    item_ids: fields.Field[list[str]] = fields.JSONField(default=[])
