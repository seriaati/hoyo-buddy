# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.exceptions import IntegrityError

from hoyo_buddy.enums import Game

from .base import BaseModel

if TYPE_CHECKING:
    from .hoyo_account import HoyoAccount


class GachaStats(BaseModel):
    account_id = fields.IntField()
    lifetime_pulls = fields.IntField()
    avg_5star_pulls = fields.FloatField()
    avg_4star_pulls = fields.FloatField()
    win_rate = fields.FloatField()
    """50/50 win rate, before multiplying 100."""
    game = fields.CharEnumField(Game, max_length=32)
    banner_type = fields.IntField()

    class Meta:
        unique_together = ("account_id", "banner_type", "game")

    @classmethod
    async def create_or_update(
        cls,
        *,
        account: HoyoAccount,
        lifetime_pulls: int,
        avg_5star_pulls: float,
        avg_4star_pulls: float,
        win_rate: float,
        banner_type: int,
    ) -> None:
        try:
            await super().create(
                account_id=account.id,
                lifetime_pulls=lifetime_pulls,
                avg_5star_pulls=avg_5star_pulls,
                avg_4star_pulls=avg_4star_pulls,
                win_rate=win_rate,
                game=account.game,
                banner_type=banner_type,
            )
        except IntegrityError:
            await cls.filter(account_id=account.id, banner_type=banner_type).update(
                lifetime_pulls=lifetime_pulls,
                avg_5star_pulls=avg_5star_pulls,
                avg_4star_pulls=avg_4star_pulls,
                win_rate=win_rate,
            )
