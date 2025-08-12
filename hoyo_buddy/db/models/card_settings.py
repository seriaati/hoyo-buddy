# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from tortoise import fields

from hoyo_buddy.enums import Game

from .base import CachedModel

if TYPE_CHECKING:
    from .user import User


class CardSettings(CachedModel):
    _cache_ttl = 60 * 60 * 24
    _pks = ("character_id", "user_id", "game")

    character_id = fields.CharField(max_length=8)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="card_settings"
    )
    dark_mode = fields.BooleanField()
    custom_images: fields.Field[list[str]] = fields.JSONField(default=[])
    """URLs of custom images."""
    custom_primary_color: fields.Field[str | None] = fields.CharField(max_length=7, null=True)
    current_image: fields.Field[str | None] = fields.TextField(null=True)
    current_team_image: fields.Field[str | None] = fields.TextField(null=True)
    template = fields.CharField(max_length=32, default="hb1")
    show_rank = fields.BooleanField(default=True)
    """Whether to show the akasha rank of the character, only applies to genshin."""
    show_substat_rolls = fields.BooleanField(default=True)
    highlight_special_stats = fields.BooleanField(default=True)
    highlight_substats: fields.Field[list[int]] = fields.JSONField(default=[])
    use_m3_art = fields.BooleanField(default=False)
    """Whether to use Mindscape 3 art for the ZZZ card."""
    game: fields.Field[Game | None] = fields.CharEnumField(Game, max_length=32, null=True)

    class Meta:
        unique_together = ("character_id", "user", "game")
        ordering = ("character_id",)

    @staticmethod
    def _get_kwargs(*, character_id: str, game: Game | None, user_id: int) -> dict[str, Any]:
        kwargs = {"character_id": character_id, "user_id": user_id}
        if game is not None:
            kwargs["game"] = game
        return kwargs

    @classmethod
    async def get(cls, *, character_id: str, user_id: int, game: Game | None = None) -> Self:
        return await super().get(
            **cls._get_kwargs(character_id=character_id, game=game, user_id=user_id)
        )

    @classmethod
    async def get_or_none(
        cls, *, character_id: str, user_id: int, game: Game | None = None
    ) -> Self | None:
        return await super().get_or_none(
            **cls._get_kwargs(character_id=character_id, game=game, user_id=user_id)
        )
