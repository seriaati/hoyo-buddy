from __future__ import annotations

from typing import TYPE_CHECKING

from attr import dataclass

if TYPE_CHECKING:
    import ambr.models


__all__ = ("FarmData", "Reward")


class FarmData:
    def __init__(self, domain: ambr.models.Domain) -> None:
        self.domain = domain
        self.characters: list[ambr.models.Character] = []
        self.weapons: list[ambr.models.Weapon] = []


@dataclass(kw_only=True)
class Reward:
    name: str
    amount: int
    index: int
    claimed: bool
    icon: str
