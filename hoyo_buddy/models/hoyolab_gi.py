from __future__ import annotations

import enka
from pydantic import BaseModel

from hoyo_buddy.enums import GenshinElement

__all__ = (
    "HoyolabGIArtifact",
    "HoyolabGICharacter",
    "HoyolabGICharacterIcon",
    "HoyolabGIConst",
    "HoyolabGICostume",
    "HoyolabGIStat",
    "HoyolabGITalent",
    "HoyolabGIWeapon",
)


class HoyolabGIStat(BaseModel):
    type: enka.gi.FightPropType
    formatted_value: str


class HoyolabGIWeapon(BaseModel):
    name: str
    stats: list[HoyolabGIStat]
    icon: str
    refinement: int
    level: int
    max_level: int
    rarity: int


class HoyolabGIConst(BaseModel):
    icon: str
    unlocked: bool


class HoyolabGITalent(BaseModel):
    icon: str
    level: int
    id: int


class HoyolabGIArtifact(BaseModel):
    icon: str
    rarity: int
    level: int
    main_stat: HoyolabGIStat
    sub_stats: list[HoyolabGIStat]
    pos: int


class HoyolabGICharacterIcon(BaseModel):
    gacha: str


class HoyolabGICostume(BaseModel):
    icon: HoyolabGICharacterIcon


class HoyolabGICharacter(BaseModel):
    id: int
    name: str
    element: GenshinElement
    highest_dmg_bonus_stat: HoyolabGIStat
    stats: dict[enka.gi.FightPropType, HoyolabGIStat]
    rarity: int

    weapon: HoyolabGIWeapon
    constellations: list[HoyolabGIConst]
    talent_order: list[int]
    talents: list[HoyolabGITalent]
    artifacts: list[HoyolabGIArtifact]

    friendship_level: int
    level: int
    max_level: int
    icon: HoyolabGICharacterIcon
    costume: HoyolabGICostume | None
