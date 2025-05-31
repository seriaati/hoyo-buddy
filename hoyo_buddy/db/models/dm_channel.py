# pyright: reportAssignmentType=false
from __future__ import annotations

from tortoise import fields

from .base import BaseModel


class DMChannel(BaseModel):
    id = fields.BigIntField(pk=True, generated=False)
    user_id = fields.BigIntField()
