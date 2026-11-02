from collections import Counter
from typing import Final

import enka

from hoyo_buddy.draw.funcs.hoyo.substat_breakdown import (
    Substat,
    SubstatTotal,
    parse_stat_value,
    total_substats,
)
from hoyo_buddy.models import HoyolabGIArtifact, HoyolabGICharacter, HoyolabGIStat

ELEMENT_BG_COLORS: Final[dict[bool, dict[enka.gi.Element, str]]] = {
    False: {
        enka.gi.Element.ANEMO: "#D9FFF4",
        enka.gi.Element.GEO: "#FFEDDC",
        enka.gi.Element.CRYO: "#D9F5FF",
        enka.gi.Element.DENDRO: "#DDFFD9",
        enka.gi.Element.PYRO: "#FFDCDC",
        enka.gi.Element.HYDRO: "#D9E8FF",
        enka.gi.Element.ELECTRO: "#EDDCFF",
        enka.gi.Element.NONE: "#EDEDED",
    },
    True: {
        enka.gi.Element.ANEMO: "#486C62",
        enka.gi.Element.GEO: "#6A5B4B",
        enka.gi.Element.CRYO: "#4E6269",
        enka.gi.Element.DENDRO: "#496645",
        enka.gi.Element.PYRO: "#795252",
        enka.gi.Element.HYDRO: "#495668",
        enka.gi.Element.ELECTRO: "#534A65",
        enka.gi.Element.NONE: "#6E6E6E",
    },
}
ELEMENT_COLORS: Final[dict[enka.gi.Element, str]] = {
    enka.gi.Element.ANEMO: "#B0FBE5",
    enka.gi.Element.GEO: "#FDC287",
    enka.gi.Element.CRYO: "#B2EBFF",
    enka.gi.Element.DENDRO: "#99F5A0",
    enka.gi.Element.PYRO: "#FDA2A2",
    enka.gi.Element.HYDRO: "#B0CEFC",
    enka.gi.Element.ELECTRO: "#AAA0FF",
}
STATS_ORDER: Final[tuple[enka.gi.FightPropType, ...]] = (
    enka.gi.FightPropType.FIGHT_PROP_MAX_HP,
    enka.gi.FightPropType.FIGHT_PROP_CUR_DEFENSE,
    enka.gi.FightPropType.FIGHT_PROP_CUR_ATTACK,
    enka.gi.FightPropType.FIGHT_PROP_ELEMENT_MASTERY,
    enka.gi.FightPropType.FIGHT_PROP_CRITICAL,
    enka.gi.FightPropType.FIGHT_PROP_CRITICAL_HURT,
    enka.gi.FightPropType.FIGHT_PROP_CHARGE_EFFICIENCY,
)
ADD_HURT_ELEMENTS: Final[dict[int, str]] = {
    int(enka.gi.FightPropType.FIGHT_PROP_ICE_ADD_HURT): "Cryo",
    int(enka.gi.FightPropType.FIGHT_PROP_FIRE_ADD_HURT): "Pyro",
    int(enka.gi.FightPropType.FIGHT_PROP_WATER_ADD_HURT): "Hydro",
    int(enka.gi.FightPropType.FIGHT_PROP_WIND_ADD_HURT): "Anemo",
    int(enka.gi.FightPropType.FIGHT_PROP_ROCK_ADD_HURT): "Geo",
    int(enka.gi.FightPropType.FIGHT_PROP_ELEC_ADD_HURT): "Electro",
    int(enka.gi.FightPropType.FIGHT_PROP_GRASS_ADD_HURT): "Dendro",
    int(enka.gi.FightPropType.FIGHT_PROP_PHYSICAL_ADD_HURT): "Physical",
}
ARTIFACT_POS: Final[dict[enka.gi.EquipmentType, int]] = {
    enka.gi.EquipmentType.FLOWER: 1,
    enka.gi.EquipmentType.FEATHER: 2,
    enka.gi.EquipmentType.SANDS: 3,
    enka.gi.EquipmentType.GOBLET: 4,
    enka.gi.EquipmentType.CIRCLET: 5,
}
ARTIFACT_AFFIX_PROP_TYPES: Final[dict[int, enka.gi.StatType]] = {
    2: enka.gi.StatType.FIGHT_PROP_HP,
    3: enka.gi.StatType.FIGHT_PROP_HP_PERCENT,
    5: enka.gi.StatType.FIGHT_PROP_ATTACK,
    6: enka.gi.StatType.FIGHT_PROP_ATTACK_PERCENT,
    8: enka.gi.StatType.FIGHT_PROP_DEFENSE,
    9: enka.gi.StatType.FIGHT_PROP_DEFENSE_PERCENT,
    20: enka.gi.StatType.FIGHT_PROP_CRITICAL,
    22: enka.gi.StatType.FIGHT_PROP_CRITICAL_HURT,
    23: enka.gi.StatType.FIGHT_PROP_CHARGE_EFFICIENCY,
    24: enka.gi.StatType.FIGHT_PROP_ELEMENT_MASTERY,
}
"""Artifact sub stat affix IDs' prop codes, e.g. 501204 is a CRIT Rate (20) roll of tier 4."""


def get_substat_rolls(artifact: enka.gi.Artifact | HoyolabGIArtifact) -> list[int]:
    """Get how many times each of the artifact's sub stats was rolled, in sub stat order."""
    if isinstance(artifact, HoyolabGIArtifact):
        return [stat.rolls for stat in artifact.sub_stats]

    counts = Counter(
        ARTIFACT_AFFIX_PROP_TYPES.get(id_ // 10 % 100) for id_ in artifact.sub_stat_ids
    )
    return [counts[stat.type] for stat in artifact.sub_stats]


MAX_SUBSTAT_ROLL_VALUES: Final[dict[str, dict[int, float]]] = {
    "FIGHT_PROP_HP_PERCENT": {1: 1.46, 2: 2.33, 3: 3.5, 4: 4.66, 5: 5.83},
    "FIGHT_PROP_HP": {1: 29.88, 2: 71.7, 3: 143.4, 4: 239.0, 5: 298.75},
    "FIGHT_PROP_ATTACK_PERCENT": {1: 1.46, 2: 2.33, 3: 3.5, 4: 4.66, 5: 5.83},
    "FIGHT_PROP_ATTACK": {1: 1.95, 2: 4.67, 3: 9.34, 4: 15.56, 5: 19.45},
    "FIGHT_PROP_DEFENSE_PERCENT": {1: 1.82, 2: 2.91, 3: 4.37, 4: 5.83, 5: 7.29},
    "FIGHT_PROP_DEFENSE": {1: 2.31, 2: 5.56, 3: 11.11, 4: 18.52, 5: 23.15},
    "FIGHT_PROP_ELEMENT_MASTERY": {1: 5.83, 2: 9.33, 3: 13.99, 4: 18.65, 5: 23.31},
    "FIGHT_PROP_CRITICAL": {1: 0.97, 2: 1.55, 3: 2.33, 4: 3.11, 5: 3.89},
    "FIGHT_PROP_CRITICAL_HURT": {1: 1.94, 2: 3.11, 3: 4.66, 4: 6.22, 5: 7.77},
    "FIGHT_PROP_CHARGE_EFFICIENCY": {1: 1.62, 2: 2.59, 3: 3.89, 4: 5.18, 5: 6.48},
}
"""Artifact sub stats' highest single roll by artifact rarity, keyed by stat type name, in
breakdown order."""


def get_substat_breakdown(
    character: enka.gi.Character | HoyolabGICharacter,
) -> list[SubstatTotal[enka.gi.Stat | HoyolabGIStat]]:
    """Total each artifact sub stat across the character's artifacts."""
    substats = [
        Substat(
            key=stat.type.name,
            stat=stat,
            value=stat.value
            if isinstance(stat, enka.gi.Stat)
            else parse_stat_value(stat.formatted_value),
            is_percent=stat.formatted_value.endswith("%"),
            decimals=1 if stat.formatted_value.endswith("%") else 0,
            rolls=rolls,
            max_roll=MAX_SUBSTAT_ROLL_VALUES.get(stat.type.name, {}).get(artifact.rarity),
        )
        for artifact in character.artifacts
        for stat, rolls in zip(artifact.sub_stats, get_substat_rolls(artifact), strict=True)
    ]
    return total_substats(substats, order=MAX_SUBSTAT_ROLL_VALUES)
