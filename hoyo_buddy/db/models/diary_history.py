# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import Any

from tortoise import fields

from hoyo_buddy.enums import Game

from .base import BaseModel


class DiaryHistory(BaseModel):
    uid = fields.BigIntField(index=True)
    game = fields.CharEnumField(Game, max_length=32)
    month = fields.CharField(max_length=6)
    """Formatted as YYYYMM."""
    data: fields.Field[dict[str, Any]] = fields.JSONField()

    class Meta:
        unique_together = ("uid", "game", "month")
        ordering = ("-month",)
