from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from attr import dataclass

from hoyo_buddy.draw.static import ZZZ_V2_GAME_RECORD

if TYPE_CHECKING:
    import genshin.models


__all__ = ("WEngine", "ZZZDiscDrive", "ZZZEnkaCharacter", "ZZZSkill", "ZZZStat")


@dataclass(kw_only=True)
class ZZZEnkaCharacter:
    id: int
    name: str
    level: int
    element: genshin.models.ZZZElementType
    w_engine: WEngine | None = None
    properties: list[ZZZStat]
    discs: list[ZZZDiscDrive]
    rank: int
    skills: list[ZZZSkill]
    outfit_id: int | None
    specialty: genshin.models.ZZZSpecialty | None

    @property
    def banner_icon(self) -> str:
        if self.outfit_id:
            return str(
                ZZZ_V2_GAME_RECORD
                / f"role_vertical_painting/role_vertical_painting_{self.id}_{self.outfit_id}.png"
            )
        return str(
            ZZZ_V2_GAME_RECORD / f"role_vertical_painting/role_vertical_painting_{self.id}.png"
        )


@dataclass(kw_only=True)
class WEngine:
    icon: str
    level: int
    refinement: int
    name: str
    main_properties: list[ZZZStat]
    properties: list[ZZZStat]


@dataclass(kw_only=True)
class ZZZDiscDrive:
    id: int
    level: int
    main_properties: list[ZZZStat]
    properties: list[ZZZStat]
    rarity: Literal["B", "A", "S"]
    position: int


@dataclass(kw_only=True)
class ZZZStat:
    name: str
    type: genshin.models.ZZZPropertyType
    value: str

    @property
    def final(self) -> str:
        return self.value


@dataclass(kw_only=True)
class ZZZSkill:
    level: int
    type: genshin.models.ZZZSkillType
