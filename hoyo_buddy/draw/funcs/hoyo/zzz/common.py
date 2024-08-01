from typing import Final

from discord import utils as dutils
from genshin.models import ZZZAgentProperty, ZZZFullAgent, ZZZPropertyType, ZZZSkillType

STAT_ICONS: Final[dict[ZZZPropertyType, str]] = {
    # Disc
    ZZZPropertyType.DISC_HP: "HP.png",
    ZZZPropertyType.DISC_ATK: "ATK.png",
    ZZZPropertyType.DISC_DEF: "DEF.png",
    ZZZPropertyType.DISC_PEN: "PEN_RATIO.png",
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
    ZZZPropertyType.PEN_RATIO: "PEN_RATIO.png",
    ZZZPropertyType.IMPACT: "IMPACT.png",
}

SKILL_ORDER: Final[tuple[ZZZSkillType, ...]] = (
    ZZZSkillType.BASIC_ATTACK,
    ZZZSkillType.DODGE,
    ZZZSkillType.ASSIST,
    ZZZSkillType.SPECIAL_ATTACK,
    ZZZSkillType.CHAIN_ATTACK,
    ZZZSkillType.CORE_SKILL,
)


def get_props(agent: ZZZFullAgent) -> tuple[ZZZAgentProperty | None, ...]:
    return (
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_HP),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ATK),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_DEF),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_IMPACT),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_RATE),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_MASTERY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_PEN_RATIO),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_ENERGY_GEN),
        dutils.get(agent.properties, type=ZZZPropertyType.AGENT_CRIT_DMG),
    )
