from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import enka
from discord.utils import get as dget

from hoyo_buddy import models as hb_models
from hoyo_buddy.constants import (
    GPY_TYPE_TO_YATTA_PROP_TYPE,
    HSR_ELEMENT_DMG_PROPS,
    MAX_SUBSTAT_ROLLS,
)
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.draw.funcs.hoyo.substat_breakdown import (
    Substat,
    SubstatTotal,
    parse_stat_value,
    total_substats,
)
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from PIL import Image


def strip_mode_suffix(floor_name: str) -> str:
    """Remove a trailing 'Regular Mode' or 'Starward Mode' label, e.g. '(IV)Starward Mode' -> '(IV)'.

    Labels of every locale are checked since the API can return a different language than the
    user's locale.
    """
    labels = {
        LocaleStr(key=key, mi18n_game=Game.STARRAIL).translate(locale).strip()
        for key in ("abyss_standard_mode", "abyss_star_mode")
        for locale in Locale
    }
    for label in sorted(labels, key=len, reverse=True):
        if label and floor_name.endswith(label):
            return floor_name.removesuffix(label).strip()
    return floor_name


@dataclass
class LevelBubble:
    short_name: str


@dataclass
class BigBubble:
    short_name: str


@dataclass
class SmallBubble:
    short_name: str


@dataclass
class BubbleWithTrace:
    bubble: LevelBubble | BigBubble | SmallBubble
    trace: enka.hsr.character.Trace | hb_models.Trace


# Hakushin is dead and we are so fucked

SHORT_NAME_TO_ANCHOR = {
    "Knight": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "D5": "Point06",
        "D2": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "D6": "Point10",
        "D7": "Point11",
        "E1": "Point12",
        "D3": "Point13",
        "D4": "Point14",
        "C1": "Point15",
        "B2": "Point16",
        "B4": "Point17",
        "B3": "Point18",
    },
    "Mage": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "E1": "Point06",
        "C1": "Point07",
        "B1": "Point08",
        "D2": "Point09",
        "E2": "Point10",
        "E3": "Point11",
        "E4": "Point12",
        "C2": "Point13",
        "C3": "Point14",
        "C4": "Point15",
        "B3": "Point16",
        "B2": "Point17",
        "D1": "Point18",
    },
    "Priest": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "D3": "Point06",
        "D7": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "D4": "Point10",
        "D5": "Point11",
        "D6": "Point12",
        "D8": "Point13",
        "D9": "Point14",
        "D10": "Point15",
        "B2": "Point16",
        "B3": "Point17",
        "D2": "Point18",
    },
    "Rogue": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "D5": "Point06",
        "D2": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "D6": "Point10",
        "D7": "Point11",
        "E1": "Point12",
        "D3": "Point13",
        "D4": "Point14",
        "C1": "Point15",
        "B2": "Point16",
        "B4": "Point17",
        "B3": "Point18",
    },
    "Shaman": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "E1": "Point06",
        "C1": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "E2": "Point10",
        "E3": "Point11",
        "D3": "Point12",
        "C2": "Point13",
        "C3": "Point14",
        "D2": "Point15",
        "B2": "Point16",
        "B4": "Point17",
        "B3": "Point18",
    },
    "Warlock": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "E1": "Point06",
        "C1": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "E2": "Point10",
        "E3": "Point11",
        "E4": "Point12",
        "C2": "Point13",
        "C3": "Point14",
        "C4": "Point15",
        "B3": "Point16",
        "B2": "Point17",
        "D2": "Point18",
    },
    "Warrior": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "D6": "Point06",
        "D2": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "D7": "Point10",
        "D8": "Point11",
        "D9": "Point12",
        "D3": "Point13",
        "D4": "Point14",
        "D5": "Point15",
        "B2": "Point16",
        "B4": "Point17",
        "B3": "Point18",
    },
    "Memory": {
        "A": "Point03",
        "B": "Point04",
        "C": "Point02",
        "D": "Point05",
        "E": "Point01",
        "E1": "Point06",
        "C1": "Point07",
        "B1": "Point08",
        "D1": "Point09",
        "D2": "Point10",
        "D3": "Point11",
        "E4": "Point12",
        "C2": "Point13",
        "C3": "Point14",
        "C4": "Point15",
        "B2": "Point16",
        "B3": "Point17",
        "B4": "Point18",
        "F1": "Point19",
        "F2": "Point20",
        "F3": "Point21",
    },
    "Elation": {
        "A": "Point01",  # Normal attack
        "B": "Point02",  # Skill
        "C": "Point03",  # Ultimate
        "D": "Point04",  # Talent
        "E": "Point05",  # Technique
        "E1": "Point06",
        "A1": "Point07",
        "B1": "Point08",
        "E3": "Point09",
        "E2": "Point10",
        "E5": "Point11",
        "E4": "Point12",
        "A2": "Point13",
        "A3": "Point14",
        "A4": "Point15",
        "B2": "Point16",
        "B3": "Point17",
        "B4": "Point18",
        "F1": "Point22",
    },
}


# fmt: off
PATH_BUBBLES = {
    "Warlock": (
        (
            LevelBubble("E"),
            BigBubble("E1"),
            SmallBubble("E2"),
            SmallBubble("E3"),
            SmallBubble("E4"),
        ),
        (
            LevelBubble("C"),
            BigBubble("C1"),
            SmallBubble("C2"),
            SmallBubble("C3"),
            SmallBubble("C4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
            SmallBubble("D2"),
        ),
    ),
    "Rogue": (
        (
            LevelBubble("E"),
            BigBubble("D5"),
            SmallBubble("E1"),
            SmallBubble("D6"),
            SmallBubble("D7"),
        ),
        (
            LevelBubble("C"),
            BigBubble("D2"),
            SmallBubble("C1"),
            SmallBubble("D3"),
            SmallBubble("D4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
        ),
    ),
    "Warrior": (
        (
            LevelBubble("E"),
            BigBubble("D6"),
            SmallBubble("D7"),
            SmallBubble("D8"),
            SmallBubble("D9"),
        ),
        (
            LevelBubble("C"),
            BigBubble("D2"),
            SmallBubble("D3"),
            SmallBubble("D4"),
            SmallBubble("D5"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
        ),
    ),
    "Knight": (
        (
            LevelBubble("E"),
            BigBubble("D5"),
            SmallBubble("E1"),
            SmallBubble("D6"),
            SmallBubble("D7"),
        ),
        (
            LevelBubble("C"),
            BigBubble("D2"),
            SmallBubble("C1"),
            SmallBubble("D3"),
            SmallBubble("D4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
        ),
    ),
    "Memory": (
        (
            LevelBubble("E"),
            SmallBubble("D1"),
            SmallBubble("D2"),
            SmallBubble("D3"),
        ),
        (
            LevelBubble("C"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
            SmallBubble("B4"),
        ),
        (
            LevelBubble("A"),
            BigBubble("C1"),
            SmallBubble("C3"),
            SmallBubble("C4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("E1"),
            SmallBubble("C2"),
            SmallBubble("E4"),
        ),
    ),
    "Shaman": (
        (
            LevelBubble("E"),
            BigBubble("E1"),
            SmallBubble("E2"),
            SmallBubble("E3"),
        ),
        (
            LevelBubble("C"),
            BigBubble("C1"),
            SmallBubble("C2"),
            SmallBubble("C3"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
            SmallBubble("D2"),
            SmallBubble("D3"),
        ),
    ),
    "Mage": (
        (
            LevelBubble("E"),
            BigBubble("E1"),
            SmallBubble("E2"),
            SmallBubble("E3"),
            SmallBubble("E4"),
        ),
        (
            LevelBubble("C"),
            BigBubble("C1"),
            SmallBubble("C2"),
            SmallBubble("C3"),
            SmallBubble("C4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
            SmallBubble("D2"),
        ),
    ),
    "Priest": (
        (
            LevelBubble("E"),
            BigBubble("D7"),
            SmallBubble("D8"),
            SmallBubble("D9"),
            SmallBubble("D10"),
        ),
        (
            LevelBubble("C"),
            BigBubble("D3"),
            SmallBubble("D4"),
            SmallBubble("D5"),
            SmallBubble("D6"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
        ),
        (
            LevelBubble("A"),
            SmallBubble("D1"),
            SmallBubble("D2"),
        ),
    ),
    "Elation": (
        (
            LevelBubble("A"),
            BigBubble("A1"),
            SmallBubble("A2"),
            SmallBubble("A3"),
            SmallBubble("A4"),
        ),
        (
            LevelBubble("B"),
            BigBubble("B1"),
            SmallBubble("B2"),
            SmallBubble("B3"),
            SmallBubble("B4"),
        ),
        (
            LevelBubble("C"),
            BigBubble("E1"),
            SmallBubble("E4"),
            SmallBubble("E5"),
        ),
        (
            LevelBubble("D"),
            SmallBubble("E2"),
            SmallBubble("E3"),
        ),
    )
}
# fmt: on

type StatOrTrace = enka.hsr.Stat | hb_models.Stat | enka.hsr.character.Trace | hb_models.Trace


def get_substat_rolls(relic: enka.hsr.Relic | hb_models.Relic) -> list[int]:
    """Get how many times each of the relic's sub stats was rolled, in sub stat order."""
    if isinstance(relic, enka.hsr.Relic):
        return [affix.cnt for affix in relic.sub_affix_list]
    return [stat.rolls for stat in relic.sub_stats]


def _get_relic_rarity(relic: enka.hsr.Relic | hb_models.Relic) -> int:
    if isinstance(relic, enka.hsr.Relic):
        # enka-py's rarity falls back to 3 for relics missing from its data, relic IDs start
        # with rarity + 1
        return int(str(relic.id)[0]) - 1
    return relic.rarity


def get_max_substat_rolls(relic: enka.hsr.Relic | hb_models.Relic) -> int:
    """Get the most times one of the relic's sub stats can be rolled."""
    return MAX_SUBSTAT_ROLLS[_get_relic_rarity(relic)]


MAX_SUBSTAT_ROLL_VALUES: Final[dict[str, dict[int, float]]] = {
    "HPAddedRatio": {2: 1.728, 3: 2.592, 4: 3.456, 5: 4.32},
    "HPDelta": {2: 16.935, 3: 25.4025, 4: 33.87, 5: 42.33752},
    "AttackAddedRatio": {2: 1.728, 3: 2.592, 4: 3.456, 5: 4.32},
    "AttackDelta": {2: 8.467512, 3: 12.70126, 4: 16.935, 5: 21.16876},
    "DefenceAddedRatio": {2: 2.16, 3: 3.24, 4: 4.32, 5: 5.4},
    "DefenceDelta": {2: 8.467512, 3: 12.70126, 4: 16.935, 5: 21.16876},
    "SpeedDelta": {2: 1.2, 3: 1.4, 4: 2.0, 5: 2.6},
    "CriticalChance": {2: 1.296, 3: 1.944, 4: 2.592, 5: 3.24},
    "CriticalDamage": {2: 2.592, 3: 3.888, 4: 5.184, 5: 6.48},
    "StatusProbability": {2: 1.728, 3: 2.592, 4: 3.456, 5: 4.32},
    "StatusResistance": {2: 1.728, 3: 2.592, 4: 3.456, 5: 4.32},
    "BreakDamageAddedRatio": {2: 2.592, 3: 3.888, 4: 5.184, 5: 6.48},
}
"""Relic sub stats' highest single roll by relic rarity, keyed by enka stat type, in breakdown
order."""

FLAT_SUBSTATS: Final = frozenset({"HPDelta", "AttackDelta", "DefenceDelta"})


def _get_substat_key(stat: enka.hsr.Stat | hb_models.Stat) -> str:
    if isinstance(stat, enka.hsr.Stat):
        return stat.type.value
    # HoYoLAB property types map to Yatta's names, which are enka's with a lowercase first letter
    name = GPY_TYPE_TO_YATTA_PROP_TYPE.get(stat.type, "")
    return name[:1].upper() + name[1:]


def _get_substat(
    stat: enka.hsr.Stat | hb_models.Stat, *, rolls: int, rarity: int
) -> Substat[str, enka.hsr.Stat | hb_models.Stat]:
    key = _get_substat_key(stat)
    if isinstance(stat, enka.hsr.Stat):
        value = stat.value * 100 if stat.is_percentage else stat.value
        precise = True
    else:
        value = parse_stat_value(stat.formatted_value)
        # HoYoLAB rounds SPD to a whole number
        precise = key != "SpeedDelta"

    return Substat(
        key=key,
        stat=stat,
        value=value,
        is_percent=stat.formatted_value.endswith("%"),
        decimals=0 if key in FLAT_SUBSTATS or not precise else 1,
        rolls=rolls,
        max_roll=MAX_SUBSTAT_ROLL_VALUES.get(key, {}).get(rarity) if precise else None,
    )


def get_substat_breakdown(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> list[SubstatTotal[enka.hsr.Stat | hb_models.Stat]]:
    """Total each relic sub stat across the character's relics."""
    substats = [
        _get_substat(stat, rolls=rolls, rarity=_get_relic_rarity(relic))
        for relic in character.relics
        # enka relics' sub stats and roll counts come from different lists
        for stat, rolls in zip(relic.sub_stats, get_substat_rolls(relic), strict=False)
    ]
    return total_substats(substats, order=MAX_SUBSTAT_ROLL_VALUES)


def get_stat_icon_filename(stat: enka.hsr.Stat | hb_models.Stat) -> str:
    return stat.type.value if isinstance(stat, enka.hsr.Stat) else stat.icon


def get_light_cone_name(light_cone: enka.hsr.LightCone | hb_models.LightCone) -> str:
    # enka leaves the text map hash as the name when the light cone's asset data is missing
    if isinstance(light_cone, enka.hsr.LightCone) and light_cone.path is enka.hsr.Path.NONE:
        return "???"
    return light_cone.name


def get_stat_icon(
    stat: StatOrTrace | None = None,
    filename: str | None = None,
    *,
    size: tuple[int, int],
    mask_color: tuple[int, int, int] | None = None,
) -> Image.Image:
    if stat is None and filename is None:
        msg = "Either 'stat' or 'filename' must be provided."
        raise ValueError(msg)

    if isinstance(stat, (enka.hsr.character.Trace, hb_models.Trace)):
        if "SkillIcon" in stat.icon or isinstance(
            stat, hb_models.Trace
        ):  # Hoyolab icon names are random strings
            return Drawer.open_static(stat.icon, size=size, mask_color=mask_color)
        return get_stat_icon(filename=stat.icon.split("/")[-1], size=size, mask_color=mask_color)

    if filename is None and stat is not None:
        filename = get_stat_icon_filename(stat)

    assert filename is not None

    filename = filename.removeprefix("Icon").removesuffix(".png")

    if filename == "EnergyRecovery":
        filename = "sPRatio"
    elif filename == "BreakUp":
        filename = "breakDamageAddedRatio"

    # Handle cases for Enka stats which start with uppercase letters (e.g., "Attack", "Defence")
    # but the actual filenames start with lowercase letters (e.g., "attack", "defence")
    filename = filename[0].lower() + filename[1:]

    return Drawer.open_image(
        f"hoyo-buddy-assets/assets/hsr-stats/{filename}.png", size=size, mask_color=mask_color
    )


def get_character_stats(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> tuple[dict[str, str], enka.hsr.character.Stat | hb_models.Stat | None]:
    stats: dict[str, str] = {}
    if isinstance(character, enka.hsr.Character):
        stat_types = (
            enka.hsr.StatType.MAX_HP,
            enka.hsr.StatType.ATK,
            enka.hsr.StatType.CRIT_RATE,
            enka.hsr.StatType.EFFECT_HIT_RATE,
            enka.hsr.StatType.BREAK_EFFECT,
            enka.hsr.StatType.ENERGY_REGEN_RATE,
            enka.hsr.StatType.DEF,
            enka.hsr.StatType.SPD,
            enka.hsr.StatType.CRIT_DMG,
            enka.hsr.StatType.EFFECT_RES,
            enka.hsr.StatType.HEALING_BOOST,
            enka.hsr.StatType.ELATION_DMG_BOOST,
        )

        for stat_type in stat_types:
            stat = character.stats.get(stat_type)
            if stat is None:
                continue
            stats[get_stat_icon_filename(stat)] = stat.formatted_value

        # enka leaves stats empty when asset data is missing, the property is then a zero placeholder
        max_dmg_add = character.highest_dmg_bonus_stat if character.stats else None
        if max_dmg_add is not None:
            stats[get_stat_icon_filename(max_dmg_add)] = max_dmg_add.formatted_value
    else:
        attr_types = (1, 2, 5, 10, 58, 9, 3, 4, 6, 11, 7, 71)
        for attr_type in attr_types:
            stat = next((s for s in character.stats if s.type == attr_type), None)
            if stat is None:
                continue
            stats[get_stat_icon_filename(stat)] = stat.formatted_value

        # Get max damage addition
        dmg_additions = [s for s in character.stats if s.type in HSR_ELEMENT_DMG_PROPS]
        if dmg_additions:
            max_dmg_add = max(dmg_additions, key=lambda a: a.formatted_value)
            stats[get_stat_icon_filename(max_dmg_add)] = max_dmg_add.formatted_value
        else:
            max_dmg_add = None

    zero_values = {"0", "0.0%", "0.0"}
    zero_stats = {k: v for k, v in stats.items() if v in zero_values}
    nonzero_stats = {k: v for k, v in stats.items() if v not in zero_values}

    if len(nonzero_stats) >= 12:
        stats = dict(list(nonzero_stats.items())[:12])
    else:
        stats = dict(nonzero_stats)
        all_keys = list(stats.keys()) + list(zero_stats.keys())
        for k in all_keys:
            if len(stats) >= 12:
                break
            if k not in stats and k in zero_stats:
                stats[k] = zero_stats[k]

    return stats, max_dmg_add


def get_character_skills(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> list[list[BubbleWithTrace]]:
    path_bubbles = PATH_BUBBLES.get(character.path)
    if path_bubbles is None:
        return []

    bubbles_with_traces: list[list[BubbleWithTrace]] = []

    for bubble_group in path_bubbles:
        group_with_traces: list[BubbleWithTrace] = []

        for bubble in bubble_group:
            anchor = SHORT_NAME_TO_ANCHOR[character.path].get(bubble.short_name)
            trace = dget(character.traces, anchor=anchor)
            if trace is None:
                continue
            group_with_traces.append(BubbleWithTrace(bubble=bubble, trace=trace))

        bubbles_with_traces.append(group_with_traces)

    return bubbles_with_traces


def get_ex_eidolon_icon(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> str | None:
    if isinstance(character, hb_models.HoyolabHSRCharacter):
        return character.ex_eidolon.icon if character.ex_eidolon is not None else None
    return character.affinitive_eidolons[0].icon if character.affinitive_eidolons else None
