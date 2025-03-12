from __future__ import annotations

from typing import Final

import enka

ELEMENT_BG_COLORS: Final[dict[bool, dict[enka.gi.Element, str]]] = {
    False: {
        enka.gi.Element.ANEMO: "#D9FFF4",
        enka.gi.Element.GEO: "#FFEDDC",
        enka.gi.Element.CRYO: "#D9F5FF",
        enka.gi.Element.DENDRO: "#DDFFD9",
        enka.gi.Element.PYRO: "#FFDCDC",
        enka.gi.Element.HYDRO: "#D9E8FF",
        enka.gi.Element.ELECTRO: "#EDDCFF",
    },
    True: {
        enka.gi.Element.ANEMO: "#486C62",
        enka.gi.Element.GEO: "#6A5B4B",
        enka.gi.Element.CRYO: "#4E6269",
        enka.gi.Element.DENDRO: "#496645",
        enka.gi.Element.PYRO: "#795252",
        enka.gi.Element.HYDRO: "#495668",
        enka.gi.Element.ELECTRO: "#534A65",
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
}
ARTIFACT_POS: Final[dict[enka.gi.EquipmentType, int]] = {
    enka.gi.EquipmentType.FLOWER: 1,
    enka.gi.EquipmentType.FEATHER: 2,
    enka.gi.EquipmentType.SANDS: 3,
    enka.gi.EquipmentType.GOBLET: 4,
    enka.gi.EquipmentType.CIRCLET: 5,
}
