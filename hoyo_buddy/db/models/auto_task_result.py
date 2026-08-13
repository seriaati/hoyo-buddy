# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from hoyo_buddy.utils import get_now

from .base import BaseModel

if TYPE_CHECKING:
    from hoyo_buddy.types import AutoTaskType

    from .hoyo_account import HoyoAccount


class AutoTaskResult(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="auto_task_results"
    )
    task_type: AutoTaskType = fields.CharField(max_length=20)
    success = fields.BooleanField()
    completed_at = fields.DatetimeField()

    account_id: int

    class Meta:
        unique_together = ("account", "task_type")

    @classmethod
    async def record(cls, *, account_id: int, task_type: AutoTaskType, success: bool) -> None:
        await cls.update_or_create(
            account_id=account_id,
            task_type=task_type,
            defaults={"success": success, "completed_at": get_now()},
        )
