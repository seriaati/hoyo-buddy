from __future__ import annotations

from typing import TYPE_CHECKING

from attr import dataclass

if TYPE_CHECKING:
    import enka


__all__ = ("Eidolon", "HoyolabHSRCharacter", "LightCone", "LightConeIcon", "Relic", "Stat", "Trace")


class LightConeIcon:
    def __init__(self, id_: int) -> None:
        self._id = id_

    @property
    def image(self) -> str:
        return f"https://sr.yatta.moe/hsr/assets/UI//equipment/large/{self._id}.png"

    @property
    def item(self) -> str:
        return f"https://api.yatta.top/hsr/assets/UI/equipment/medium/{self._id}.png"


@dataclass(kw_only=True)
class LightCone:
    id: int
    level: int
    superimpose: int
    name: str
    max_level: int
    rarity: int
    stats: list[Stat]

    @property
    def icon(self) -> LightConeIcon:
        return LightConeIcon(self.id)


@dataclass(kw_only=True)
class Stat:
    type: int
    icon: str
    formatted_value: str


@dataclass(kw_only=True)
class Relic:
    id: int
    level: int
    rarity: int
    icon: str
    main_stat: Stat
    sub_stats: list[Stat]
    type: enka.hsr.RelicType


@dataclass(kw_only=True)
class Trace:
    anchor: str
    icon: str
    level: int


@dataclass(kw_only=True)
class Eidolon:
    icon: str
    unlocked: bool


@dataclass(kw_only=True)
class HoyolabHSRCharacter:
    id: str
    name: str
    level: int
    eidolons_unlocked: int
    light_cone: LightCone | None = None
    relics: list[Relic]
    stats: list[Stat]
    traces: list[Trace]
    eidolons: list[Eidolon]
    element: str
    max_level: int
    rarity: int
    path: enka.hsr.Path
