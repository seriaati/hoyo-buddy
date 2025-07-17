from __future__ import annotations

from typing import Literal

import genshin.models
from pydantic import BaseModel, field_validator

__all__ = ("UnownedGICharacter", "UnownedHSRCharacter", "UnownedZZZCharacter")


class UnownedGICharacter(BaseModel):
    id: str
    element: str
    rarity: int
    level: int = 0
    friendship: int = 0
    constellation: int = 0
    weapon_type: int


class UnownedHSRCharacter(BaseModel):
    id: int
    element: str
    rarity: int
    path: genshin.models.StarRailPath
    level: int = 0
    rank: int = 0

    @field_validator("element", mode="before")
    @classmethod
    def __transform_element_name(cls, v: str) -> str:
        if v.lower() == "thunder":
            return "lightning"
        return v.lower()


class UnownedZZZCharacter(BaseModel):
    id: int
    element: genshin.models.ZZZElementType
    rarity: Literal["S", "A"]
    level: int = 0
    specialty: genshin.models.ZZZSpecialty
    faction_name: str
    rank: int = 0
    banner_icon: str
    w_engine: None = None
