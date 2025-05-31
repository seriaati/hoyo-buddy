# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import Any

from tortoise import fields
from tortoise.exceptions import IntegrityError

from hoyo_buddy.enums import Game, LeaderboardType

from .base import BaseModel


class Leaderboard(BaseModel):
    type = fields.CharEnumField(LeaderboardType, max_length=32)
    game = fields.CharEnumField(Game, max_length=32)
    value = fields.FloatField()
    uid = fields.BigIntField()
    rank = fields.IntField()
    username = fields.CharField(max_length=32)
    extra_info: fields.Field[dict[str, Any]] = fields.JSONField(default={}, null=True)

    class Meta:
        unique_together = ("type", "game", "uid")

    @classmethod
    async def update_or_create(
        cls,
        *,
        type_: LeaderboardType,
        game: Game,
        uid: int,
        value: float,
        username: str,
        extra_info: dict[str, Any] | None,
    ) -> None:
        extra_info = extra_info or {}

        try:
            await cls.create(
                type=type_,
                game=game,
                uid=uid,
                value=value,
                username=username,
                rank=0,
                extra_info=extra_info,
            )
        except IntegrityError:
            lb = await cls.get(type=type_, game=game, uid=uid)
            if lb.value < value:
                await cls.filter(type=type_, game=game, uid=uid).update(
                    value=value, username=username, extra_info=extra_info
                )
