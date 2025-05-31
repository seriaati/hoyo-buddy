# pyright: reportAssignmentType=false
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from tortoise import exceptions, fields

from .base import BaseModel

if TYPE_CHECKING:
    from .user import User


class CustomImage(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    name: fields.Field[str | None] = fields.CharField(max_length=100, null=True)
    url = fields.TextField(null=True)

    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="custom_images"
    )

    class Meta:
        unique_together = ("character_id", "user", "url")
        ordering = ("character_id", "id")

    @classmethod
    async def create(
        cls, *, url: str, character_id: str, user_id: int, name: str | None = None
    ) -> None:
        with contextlib.suppress(exceptions.IntegrityError):
            await super().create(url=url, character_id=character_id, user_id=user_id, name=name)
