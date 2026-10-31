from __future__ import annotations

import datetime

from pydantic import BaseModel

from hoyo_buddy.enums import FiftyFiftyResult, GachaItemKind, Game

__all__ = ("GachaRank", "GachaSummary", "GachaSummaryItem")


class GachaRank(BaseModel):
    rank: int
    total: int

    @property
    def percent(self) -> float:
        """The X in 'Top X%'."""
        return round(self.rank / self.total * 100, 2)


class GachaSummaryItem(BaseModel):
    """A 5-star (S-rank) pull shown on the gacha summary card."""

    item_id: int
    name: str
    kind: GachaItemKind
    pulls: int
    """Number of pulls it took to get this item."""
    result: FiftyFiftyResult | None
    """None on banners without a 50/50 (or 75/25)."""
    time: datetime.datetime

    art_url: str = ""
    """Large art, only drawn for the latest pull. Filled by the game's art resolver."""
    icon_url: str = ""
    """Small portrait for the previous pulls row. Filled by the game's art resolver."""


class GachaSummary(BaseModel):
    game: Game
    banner_type: int
    banner_name: str
    """Already translated."""

    nickname: str
    uid: int
    avatar_url: str

    five_star_pity: int
    five_star_max_pity: int
    five_star_soft_pity: int | None
    four_star_pity: int
    four_star_max_pity: int

    win_rate_title: str | None
    """'50/50' or '75/25', None on banners without one."""
    guaranteed: bool

    banner_pulls: int
    banner_currency: int
    lifetime_pulls: int
    lifetime_currency: int

    total_five_stars: int
    total_four_stars: int
    avg_five_star_pulls: float
    avg_four_star_pulls: float

    fifty_fifty_wins: int
    fifty_fifty_total: int

    lifetime_rank: GachaRank | None
    five_star_luck_rank: GachaRank | None
    four_star_luck_rank: GachaRank | None
    win_rate_rank: GachaRank | None

    latest: GachaSummaryItem | None
    previous: list[GachaSummaryItem]
    """Up to 5 pulls before the latest one, newest first."""

    # Only used by the stats embed for Genshin's Miliastra Wonderland Standard Ode banner,
    # which drops 4 and 3 stars instead of 5 and 4 stars
    is_standard_ode: bool
    three_star_pity: int
    three_star_max_pity: int
    total_three_stars: int
    avg_three_star_pulls: float
    three_star_luck_rank: GachaRank | None

    @property
    def win_rate(self) -> float:
        """0-100."""
        if not self.fifty_fifty_total:
            return 0.0
        return round(self.fifty_fifty_wins / self.fifty_fifty_total * 100, 2)
