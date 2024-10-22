from __future__ import annotations

from typing import Final

from discord import utils as dutils
from genshin.models import ZZZAgentProperty, ZZZElementType, ZZZFullAgent, ZZZPropertyType, ZZZSkillType

STAT_ICONS: Final[dict[ZZZPropertyType, str]] = {
    # Disc
    ZZZPropertyType.DISC_HP: "HP.png",
    ZZZPropertyType.DISC_ATK: "ATK.png",
    ZZZPropertyType.DISC_DEF: "DEF.png",
    ZZZPropertyType.DISC_PEN: "PEN.png",
    ZZZPropertyType.DISC_BONUS_PHYSICAL_DMG: "PHYSICAL.png",
    ZZZPropertyType.DISC_BONUS_FIRE_DMG: "FIRE.png",
    ZZZPropertyType.DISC_BONUS_ICE_DMG: "ICE.png",
    ZZZPropertyType.DISC_BONUS_ELECTRIC_DMG: "ELECTRIC.png",
    ZZZPropertyType.DISC_BONUS_ETHER_DMG: "ETHER.png",
    # W-engine
    ZZZPropertyType.ENGINE_HP: "HP.png",
    ZZZPropertyType.ENGINE_BASE_ATK: "ATK.png",
    ZZZPropertyType.ENGINE_ATK: "ATK.png",
    ZZZPropertyType.ENGINE_DEF: "DEF.png",
    ZZZPropertyType.ENGINE_ENERGY_REGEN: "ENERGY_REGEN.png",
    # Common
    ZZZPropertyType.CRIT_DMG: "CRIT_DMG.png",
    ZZZPropertyType.CRIT_RATE: "CRIT_RATE.png",
    ZZZPropertyType.ANOMALY_PROFICIENCY: "ANOMALY_PRO.png",
    ZZZPropertyType.ANOMALY_MASTERY: "ANOMALY_MASTER.png",
    ZZZPropertyType.PEN_RATIO: "PEN_RATIO.png",
    ZZZPropertyType.IMPACT: "IMPACT.png",
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
    result = [
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_HP),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ATK),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_DEF),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_IMPACT),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_RATE),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_PEN),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_MASTERY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_PEN_RATIO),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ENERGY_GEN),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_DMG),
    ]

    match agent.element:
        case ZZZElementType.PHYSICAL:
            result.append(dutils.get(agent.properties, type=ZZZPropertyType.PHYSICAL_DMG_BONUS))
        case ZZZElementType.FIRE:
            result.append(dutils.get(agent.properties, type=ZZZPropertyType.FIRE_DMG_BONUS))
        case ZZZElementType.ICE:
            result.append(dutils.get(agent.properties, type=ZZZPropertyType.ICE_DMG_BONUS))
        case ZZZElementType.ELECTRIC:
            result.append(dutils.get(agent.properties, type=ZZZPropertyType.ELECTRIC_DMG_BONUS))
        case ZZZElementType.ETHER:
            result.append(dutils.get(agent.properties, type=ZZZPropertyType.ETHER_DMG_BONUS))

    return result
