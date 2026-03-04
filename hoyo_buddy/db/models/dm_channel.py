# pyright: reportAssignmentType=false

from tortoise import fields

from .base import BaseModel


class DMChannel(BaseModel):
    id = fields.BigIntField(pk=True, generated=False)
    user_id = fields.BigIntField()
