# pyright: reportAssignmentType=false
from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.exceptions import IntegrityError

from .base import BaseModel

if TYPE_CHECKING:
    from .user import User


class CustomImage(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    name: fields.Field[str | None] = fields.CharField(max_length=100, null=True)
    url = fields.TextField(null=True)
    animated = fields.BooleanField(default=False)
    """Whether the image is an animated WEBP converted from a sponsor's upload."""
    zoom = fields.SmallIntField(default=100)
    """Zoom of the animated image in percent, 100 covers the card's image mask."""
    focus_x = fields.SmallIntField(default=50)
    """Horizontal position of the animated image in the image mask in percent, 0 is left."""
    focus_y = fields.SmallIntField(default=50)
    """Vertical position of the animated image in the image mask in percent, 0 is top."""

    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="custom_images"
    )

    class Meta:
        unique_together = ("character_id", "user", "url")
        ordering = ("character_id", "id")

    @classmethod
    async def create(
        cls,
        *,
        url: str,
        character_id: str,
        user_id: int,
        name: str | None = None,
        animated: bool = False,
    ) -> None:
        with contextlib.suppress(IntegrityError):
            await super().create(
                url=url, character_id=character_id, user_id=user_id, name=name, animated=animated
            )
