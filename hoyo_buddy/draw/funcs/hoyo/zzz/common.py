from __future__ import annotations

from typing import Final

from discord import utils as dutils
from genshin.models import (
    ZZZAgentProperty,
    ZZZElementType,
    ZZZFullAgent,
    ZZZPropertyType,
    ZZZSkillType,
)

STAT_ICONS: Final[dict[ZZZPropertyType, str]] = {
    # Disc and w-engine
    ZZZPropertyType.BASE_ATK: "ATK.png",
    ZZZPropertyType.FLAT_HP: "HP.png",
    ZZZPropertyType.FLAT_ATK: "ATK.png",
    ZZZPropertyType.FLAT_DEF: "DEF.png",
    ZZZPropertyType.FLAT_PEN: "PEN.png",
    ZZZPropertyType.HP_PERCENT: "HP.png",
    ZZZPropertyType.ATK_PERCENT: "ATK.png",
    ZZZPropertyType.DEF_PERCENT: "DEF.png",
    ZZZPropertyType.PEN_PERCENT: "PEN_RATIO.png",
    ZZZPropertyType.DISC_PHYSICAL_DMG_BONUS: "PHYSICAL.png",
    ZZZPropertyType.DISC_FIRE_DMG_BONUS: "FIRE.png",
    ZZZPropertyType.DISC_ICE_DMG_BONUS: "ICE.png",
    ZZZPropertyType.DISC_ELECTRIC_DMG_BONUS: "ELECTRIC.png",
    ZZZPropertyType.DISC_ETHER_DMG_BONUS: "ETHER.png",
    ZZZPropertyType.CRIT_DMG: "CRIT_DMG.png",
    ZZZPropertyType.CRIT_RATE: "CRIT_RATE.png",
    ZZZPropertyType.ANOMALY_PROFICIENCY: "ANOMALY_PRO.png",
    ZZZPropertyType.ANOMALY_MASTERY: "ANOMALY_MASTER.png",
    ZZZPropertyType.IMPACT: "IMPACT.png",
    ZZZPropertyType.ENERGY_REGEN: "ENERGY_REGEN.png",
    # Agent
    ZZZPropertyType.AGENT_HP: "HP.png",
    ZZZPropertyType.AGENT_ATK: "ATK.png",
    ZZZPropertyType.AGENT_DEF: "DEF.png",
    ZZZPropertyType.AGENT_PEN: "PEN.png",
    ZZZPropertyType.AGENT_PEN_RATIO: "PEN_RATIO.png",
    ZZZPropertyType.AGENT_CRIT_RATE: "CRIT_RATE.png",
    ZZZPropertyType.AGENT_CRIT_DMG: "CRIT_DMG.png",
    ZZZPropertyType.AGENT_ENERGY_GEN: "ENERGY_REGEN.png",
    ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY: "ANOMALY_PRO.png",
    ZZZPropertyType.AGENT_ANOMALY_MASTERY: "ANOMALY_MASTER.png",
    ZZZPropertyType.AGENT_IMPACT: "IMPACT.png",
    # Agent DMG Bonus
    ZZZPropertyType.PHYSICAL_DMG_BONUS: "PHYSICAL.png",
    ZZZPropertyType.FIRE_DMG_BONUS: "FIRE.png",
    ZZZPropertyType.ICE_DMG_BONUS: "ICE.png",
    ZZZPropertyType.ELECTRIC_DMG_BONUS: "ELECTRIC.png",
    ZZZPropertyType.ETHER_DMG_BONUS: "ETHER.png",
}


SKILL_ORDER: Final[tuple[ZZZSkillType, ...]] = (
    ZZZSkillType.BASIC_ATTACK,
    ZZZSkillType.DODGE,
    ZZZSkillType.ASSIST,
    ZZZSkillType.SPECIAL_ATTACK,
    ZZZSkillType.CHAIN_ATTACK,
    ZZZSkillType.CORE_SKILL,
)


def get_props(agent: ZZZFullAgent) -> list[ZZZAgentProperty | None]:
    props = [
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_HP),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_DEF),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ATK),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_IMPACT),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ENERGY_GEN),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_MASTERY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_RATE),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_DMG),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_PEN),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_PEN_RATIO),
    ]

    dmg_index = 4
    match agent.element:
        case ZZZElementType.PHYSICAL:
            props.insert(
                dmg_index, dutils.get(agent.properties, type=ZZZPropertyType.PHYSICAL_DMG_BONUS)
            )
        case ZZZElementType.FIRE:
            props.insert(
                dmg_index, dutils.get(agent.properties, type=ZZZPropertyType.FIRE_DMG_BONUS)
            )
        case ZZZElementType.ICE:
            props.insert(
                dmg_index, dutils.get(agent.properties, type=ZZZPropertyType.ICE_DMG_BONUS)
            )
        case ZZZElementType.ELECTRIC:
            props.insert(
                dmg_index, dutils.get(agent.properties, type=ZZZPropertyType.ELECTRIC_DMG_BONUS)
            )
        case ZZZElementType.ETHER:
            props.insert(
                dmg_index, dutils.get(agent.properties, type=ZZZPropertyType.ETHER_DMG_BONUS)
            )

    return props
