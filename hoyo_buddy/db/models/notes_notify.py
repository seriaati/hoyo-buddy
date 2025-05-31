# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from hoyo_buddy.enums import NotesNotifyType

from .base import BaseModel

if TYPE_CHECKING:
    import datetime

    from .hoyo_account import HoyoAccount


class NotesNotify(BaseModel):
    type = fields.IntEnumField(NotesNotifyType)
    enabled = fields.BooleanField(default=True)
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="notifs"
    )

    last_notif_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    last_check_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    est_time: fields.Field[datetime.datetime | None] = fields.DatetimeField(null=True)
    """Estimated time for the threshold to be reached."""

    notify_interval = fields.SmallIntField()
    """Notify interval in minutes."""
    check_interval = fields.SmallIntField()
    """Check interval in minutes."""

    max_notif_count = fields.SmallIntField(default=5)
    current_notif_count = fields.SmallIntField(default=0)

    threshold: fields.Field[int | None] = fields.SmallIntField(null=True)
    """For resin, realm currency, trailblaze power, and reservered trailblaze power."""
    notify_time: fields.Field[int | None] = fields.SmallIntField(null=True)
    """X hour before server resets. For dailies, resin discount, and echo of war."""
    notify_weekday: fields.Field[int | None] = fields.SmallIntField(null=True)
    """For resin discount and echo of war, 1~7, 1 is Monday."""

    hours_before: fields.Field[int | None] = fields.SmallIntField(null=True)
    """Notify X hours before the event. For plannar fissure."""

    class Meta:
        unique_together = ("type", "account")
        ordering = ("type",)
