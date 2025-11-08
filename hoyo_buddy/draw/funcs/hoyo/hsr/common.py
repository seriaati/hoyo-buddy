from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import enka
from discord.utils import get as dget

from hoyo_buddy import models as hb_models
from hoyo_buddy.constants import HSR_ELEMENT_DMG_PROPS
from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    from PIL import Image


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
}
# fmt: on

type StatOrTrace = enka.hsr.Stat | hb_models.Stat | enka.hsr.character.Trace | hb_models.Trace


def get_stat_icon_filename(stat: enka.hsr.Stat | hb_models.Stat) -> str:
    return stat.type.value if isinstance(stat, enka.hsr.Stat) else stat.icon


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
        )

        for stat_type in stat_types:
            stat = character.stats.get(stat_type)
            if stat is None:
                continue
            stats[get_stat_icon_filename(stat)] = stat.formatted_value

        max_dmg_add = character.highest_dmg_bonus_stat
        stats[get_stat_icon_filename(max_dmg_add)] = max_dmg_add.formatted_value
    else:
        attr_types = (1, 2, 5, 10, 58, 9, 3, 4, 6, 11, 7)
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
