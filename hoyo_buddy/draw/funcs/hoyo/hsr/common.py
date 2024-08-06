from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from discord.utils import get as dget

from hoyo_buddy.constants import HSR_ELEMENT_DMG_PROPS

if TYPE_CHECKING:
    from hoyo_buddy import models as hb_models


def get_character_stats(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> tuple[dict[str, str], enka.hsr.character.Stat | hb_models.Stat | None]:
    stats: dict[str, str] = {}
    if isinstance(character, enka.hsr.Character):
        stat_types = (
            enka.hsr.StatType.MAX_HP,
            enka.hsr.StatType.ATK,
            enka.hsr.StatType.DEF,
            enka.hsr.StatType.SPD,
            enka.hsr.StatType.CRIT_RATE,
            enka.hsr.StatType.CRIT_DMG,
            enka.hsr.StatType.BREAK_EFFECT,
            enka.hsr.StatType.HEALING_BOOST,
            enka.hsr.StatType.ENERGY_REGEN_RATE,
            enka.hsr.StatType.EFFECT_HIT_RATE,
            enka.hsr.StatType.EFFECT_RES,
        )
        for stat_type in stat_types:
            stat = character.stats.get(stat_type)
            if stat is None:
                continue
            stats[stat.icon] = stat.formatted_value

        max_dmg_add = character.highest_dmg_bonus_stat
        stats[max_dmg_add.icon] = max_dmg_add.formatted_value
    else:
        attr_types = (1, 2, 3, 4, 5, 6, 9, 11, 10, 58, 7)
        for attr_type in attr_types:
            stat = next((s for s in character.stats if s.type == attr_type), None)
            if stat is None:
                continue
            stats[stat.icon] = stat.formatted_value

        # Get max damage addition
        dmg_additions = [s for s in character.stats if s.type in HSR_ELEMENT_DMG_PROPS]
        if dmg_additions:
            max_dmg_add = max(dmg_additions, key=lambda a: a.formatted_value)
            stats[max_dmg_add.icon] = max_dmg_add.formatted_value
        else:
            max_dmg_add = None

    return stats, max_dmg_add


def get_character_skills(
    character: enka.hsr.Character | hb_models.HoyolabHSRCharacter,
) -> tuple[
    dict[str, enka.hsr.character.Trace | hb_models.Trace | None],
    dict[str, enka.hsr.character.Trace | hb_models.Trace | None],
    dict[str, list[enka.hsr.character.Trace | hb_models.Trace | None]],
]:
    traces = {
        "Normal": dget(character.traces, anchor="Point01"),
        "Skill": dget(character.traces, anchor="Point02"),
        "Ultimate": dget(character.traces, anchor="Point03"),
        "Talent": dget(character.traces, anchor="Point04"),
    }
    main_bubbles = {
        "Normal": dget(character.traces, anchor="Point06"),
        "Skill": dget(character.traces, anchor="Point07"),
        "Ultimate": dget(character.traces, anchor="Point08"),
        "Talent": dget(character.traces, anchor="Point05"),
    }
    sub_bubbles = {
        "Normal": [
            dget(character.traces, anchor="Point10"),
            dget(character.traces, anchor="Point11"),
            dget(character.traces, anchor="Point12"),
        ],
        "Skill": [
            dget(character.traces, anchor="Point13"),
            dget(character.traces, anchor="Point14"),
            dget(character.traces, anchor="Point15"),
        ],
        "Ultimate": [
            dget(character.traces, anchor="Point16"),
            dget(character.traces, anchor="Point17"),
            dget(character.traces, anchor="Point18"),
        ],
        "Talent": [
            dget(character.traces, anchor="Point09"),
        ],
    }
    return traces, main_bubbles, sub_bubbles
