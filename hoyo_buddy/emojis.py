from __future__ import annotations

from typing import Final

import genshin
import hakushin

from .enums import Game, GenshinCity, GenshinElement, HSRElement, HSRPath, ZZZElement

LOADING = "<a:loading_emoji:1106388708862738463>"
DELETE = "<:DELETE:1166012141833310248>"
EDIT = "<:EDIT:1166020688927260702>"
ADD = "<:ADD:1166153842816200804>"
BACK = "<:BACK:1166306958337396766>"
FORWARD = "<:FORWARD:1166687402337775646>"
REFRESH = "<:REFRESH:1166720923014021120>"
COOKIE = "<:COOKIE:1166729718431748176>"
PASSWORD = "<:PASSWORD:1166730162784710716>"
INFO = "<:INFO:1300273543803568169>"
EXPORT = "<:export2:1037927909932929144>"
SETTINGS = "<:SETTINGS:1169592948661432411>"
FREE_CANCELLATION = "<:FREE_CANCELLATION:1169597369470427246>"
BOOK_MULTIPLE = "<:bookmultiple:1067260453249618001>"
BELL_OUTLINE = "<:belloutline:1067642704814674062>"
LEFT = "<:left:982588994778972171>"
RIGHT = "<:right:982588993122238524>"
DOUBLE_LEFT = "<:double_left:982588991461281833>"
DOUBLE_RIGHT = "<:double_right:982588990223958047>"
PHONE = "<:PHONE:1222680727217377360>"
GIFT_OUTLINE = "<:giftoutline1:1067640525747933186>"
PALETTE = "<:PALETTE:1270219381296726036>"
PHOTO_ADD = "<:PHOTO_ADD:1270219386862436438>"
LINK = "<:LINK_FILL_WHITE:1281261683720847412>"
PHOTO = "<:PHOTO:1294662192322318397>"
GROUP = "<:GROUP:1298503915863543851>"
FILTER = "<:FILTER:1302287412852031598>"
REDEEM_GIFT = "<:REDEEM_GIFT:1303162563151925258>"

GITHUB_WHITE_ICON = "<:GITHUB_WHITE_ICON:1229374869435846676>"
DISCORD_WHITE_ICON = "<:DISCORD_WHITE_ICON:1229374673566044161>"

GI_EMOJI = "<:GENSHIN_IMPACT:1300364921309233204>"
HSR_EMOJI = "<:HONKAI_STAR_RAIL:1300365076003295277>"
HI3_EMOJI = "<:HONKAI_IMPACT:1300365163001544735>"
ZZZ_EMOJI = "<:ZENLESS_ZONE_ZERO:1300365249865846825>"
TOT_EMOJI = "<:TOT_ICON:1264395240001769473>"

PRIMOGEM_EMOJI = "<:PRIMOGEM:1300362870428532746>"
STELLAR_JADE_EMOJI = "<:JADE:1300363950696824887>"
POLYCHROME_EMOJI = "<:POLYCHROME:1300364352066424842>"

CURRENCY_EMOJIS: Final[dict[Game, str]] = {
    Game.GENSHIN: PRIMOGEM_EMOJI,
    Game.STARRAIL: STELLAR_JADE_EMOJI,
    Game.ZZZ: POLYCHROME_EMOJI,
}

GENSHIN_ELEMENT_EMOJIS: dict[GenshinElement, str] = {
    GenshinElement.PYRO: "<:pyro:1189150911428317275>",
    GenshinElement.HYDRO: "<:hydro:1189150893875142726>",
    GenshinElement.CRYO: "<:cryo:1189150960413573141>",
    GenshinElement.ANEMO: "<:anemo:1189150874916888636>",
    GenshinElement.DENDRO: "<:dendro:1189150946878562354>",
    GenshinElement.GEO: "<:geo:1189150979657044012>",
    GenshinElement.ELECTRO: "<:electro:1189150927190495232>",
}
GENSHIN_CITY_EMOJIS: dict[GenshinCity, str] = {
    GenshinCity.MONDSTADT: "<:Emblem_Mondstadt:982449412938809354>",
    GenshinCity.LIYUE: "<:Emblem_Liyue:982449411047165992>",
    GenshinCity.INAZUMA: "<:Emblem_Inazuma:982449409117806674>",
    GenshinCity.SUMERU: "<:Emblem_Sumeru:1217359294736105472>",
    GenshinCity.FONTAINE: "<:Emblem_Fontaine:1217359292966109205>",
    GenshinCity.NATLAN: "<:NatlanCity:1279223382378020874>",
}
HSR_ELEMENT_EMOJIS: dict[str, str] = {
    HSRElement.FIRE: "<:IconAttributeFire:1211302768862695475>",
    HSRElement.ICE: "<:IconAttributeIce:1211302446769377310>",
    HSRElement.IMAGINARY: "<:IconAttributeImaginary:1211302761912606890>",
    HSRElement.PHYSICAL: "<:IconAttributePhysical:1211302759907983461>",
    HSRElement.QUANTUM: "<:IconAttributeQuantum:1211302767033983046>",
    # HSRElement.LIGHTNING: "<:IconAttributeThunder:1211302758175735942>",
    HSRElement.WIND: "<:IconAttributeWind:1211302764915859498>",
    HSRElement.THUNDER: "<:IconAttributeThunder:1211302758175735942>",
}
HSR_PATH_EMOJIS: dict[str, str] = {
    HSRPath.DESTRUCTION: "<:DESTRUCTION:1220140640424296530>",
    HSRPath.THE_HUNT: "<:THE_HUNT:1220140785215864993>",
    HSRPath.ERUDITION: "<:ERUDITION:1220140857378734112>",
    HSRPath.HARMONY: "<:HARMONY:1220140931563389019>",
    HSRPath.NIHILITY: "<:NIHILITY:1220141009871310948>",
    HSRPath.PRESERVATION: "<:PRESERVATION:1220141073700094083>",
    HSRPath.ABUNDANCE: "<:ABUNDANCE:1220141134706118666>",
    HSRPath.REMEMBRANCE: "<:REMEMBRANCE:1313365363227889725>",
}
ZZZ_ELEMENT_EMOJIS: dict[ZZZElement, str] = {
    ZZZElement.FIRE: "<:FIRE:1261296222237626478>",
    ZZZElement.ELECTRIC: "<:ELECTRIC:1261296220249526354>",
    ZZZElement.ETHER: "<:ETHER:1261295818032549908>",
    ZZZElement.ICE: "<:ICE:1261296218101907569>",
    ZZZElement.PHYSICAL: "<:PHYSICAL:1261296216126390273>",
}
ZZZ_SPECIALTY_EMOJIS: dict[genshin.models.ZZZSpecialty, str] = {
    genshin.models.ZZZSpecialty.ANOMALY: "<:zzzProfessionNuclear:1263458200980689046>",
    genshin.models.ZZZSpecialty.ATTACK: "<:zzzProfessionSword:1263458204688318554>",
    genshin.models.ZZZSpecialty.DEFENSE: "<:zzzProfessionShield:1263458202943623208>",
    genshin.models.ZZZSpecialty.STUN: "<:zzzProfessionMace:1263458199068082207>",
    genshin.models.ZZZSpecialty.SUPPORT: "<:zzzProfessionBullet:1263458197453148191>",
}

ARTIFACT_POS_EMOJIS: dict[str, str] = {
    "flower": "<:Flower_of_Life:982167959717945374>",
    "plume": "<:Plume_of_Death:982167959915077643>",
    "sands": "<:Sands_of_Eon:982167959881547877>",
    "goblet": "<:Goblet_of_Eonothem:982167959835402240>",
    "circlet": "<:Circlet_of_Logos:982167959692787802>",
}
DICE_EMOJIS: dict[str, str] = {
    "GCG_COST_ENERGY": "<:UI_Gcg_DiceL_Energy:1300366242200293406>",
    "GCG_COST_DICE_VOID": "<:UI_Gcg_DiceL_Diff_Glow:1300366342427377725>",
    "GCG_COST_DICE_SAME": "<:UI_Gcg_DiceL_Any_Glow:1300366563328786463>",
    "GCG_COST_DICE_CRYO": "<:UI_Gcg_DiceL_Ice_Glow:1300366676059226122>",
    "GCG_COST_DICE_HYDRO": "<:UI_Gcg_DiceL_Water_Glow:1300366782887890985>",
    "GCG_COST_DICE_PYRO": "<:UI_Gcg_DiceL_Fire_Glow:1300366920884949002>",
    "GCG_COST_DICE_ELECTRO": "<:UI_Gcg_DiceL_Electric_Glow:1300367030330982422>",
    "GCG_COST_DICE_ANEMO": "<:UI_Gcg_DiceL_Wind_Glow:1300367122488102983>",
    "GCG_COST_DICE_GEO": "<:UI_Gcg_DiceL_Rock_Glow:1300367198971367434>",
    "GCG_COST_DICE_DENDRO": "<:UI_Gcg_DiceL_Grass_Glow:1300367291170553950>",
}
RELIC_POS_EMOJIS: dict[str, str] = {
    "neck": "<:IconRelicNeck:1196077198155718766>",
    "head": "<:IconRelicHead:1196077193902690344>",
    "hand": "<:IconRelicHands:1196077192136884334>",
    "object": "<:IconRelicGoods:1196077188907274422>",
    "foot": "<:IconRelicFoot:1196077185933508709>",
    "body": "<:IconRelicBody:1196077184394219600>",
}
TOGGLE_EMOJIS: dict[bool, str] = {
    False: "<:TOGGLE_OFF:1215446301202980914>",
    True: "<:TOGGLE_ON:1215289748415844382>",
}

ZZZ_SKILL_TYPE_EMOJIS: dict[hakushin.enums.ZZZSkillType, str] = {
    hakushin.enums.ZZZSkillType.ASSIST: "<:Icon_Switch:1271096975131021426>",
    hakushin.enums.ZZZSkillType.BASIC: "<:Icon_Normal:1271096817978839123>",
    hakushin.enums.ZZZSkillType.CHAIN: "<:Icon_UltimateReady:1271096958647406642>",
    hakushin.enums.ZZZSkillType.DODGE: "<:Icon_Evade:1271096823649407117>",
    hakushin.enums.ZZZSkillType.SPECIAL: "<:Icon_SpecialReady:1271096829320364213>",
}
ZZZ_SKILL_TYPE_CORE = "<:Icon_CoreSkill:1271096929014648873>"

COMFORT_ICON = "<:COMFORT:1300369174131900477>"
LOAD_ICON = "<:LOAD:1300369278259691540>"
PROJECT_AMBER = "<:PROJECT_AMBER:1191752455998930955>"

RESIN = "<:RESIN:1300369589649018935>"
REALM_CURRENCY = "<:REALM_CURRENCY:1300369688605360183>"
PT_EMOJI = "<:TRANSFORMER:1300369885641179157>"

TRAILBLAZE_POWER = "<:TB_POWER:1300370544499097601>"
RESERVED_TRAILBLAZE_POWER = "<:RTB_POWER:1300370408612171828>"

BATTERY_CHARGE_EMOJI = "<:BATTERY:1300370911064625175>"
SCRATCH_CARD_EMOJI = "<:SCRATCH_CARD:1260127526580260989>"


def get_game_emoji(game: genshin.Game | Game) -> str:
    if game is genshin.Game.GENSHIN or game is Game.GENSHIN:
        return GI_EMOJI
    if game is genshin.Game.HONKAI or game is Game.HONKAI:
        return HI3_EMOJI
    if game is genshin.Game.STARRAIL or game is Game.STARRAIL:
        return HSR_EMOJI
    if game is genshin.Game.ZZZ or game is Game.ZZZ:
        return ZZZ_EMOJI
    if game is genshin.Game.TOT or game is Game.TOT:
        return TOT_EMOJI
    return None


def get_gi_element_emoji(element: str) -> str:
    return GENSHIN_ELEMENT_EMOJIS[GenshinElement(element.title())]


def get_hsr_element_emoji(element: str) -> str:
    if element.lower() == "lightning":
        element = "thunder"
    return HSR_ELEMENT_EMOJIS[HSRElement(element.title())]


def get_zzz_element_emoji(
    element: ZZZElement
    | hakushin.enums.ZZZElement
    | hakushin.zzz.CharacterProp
    | genshin.models.ZZZElementType,
) -> str:
    name = (
        genshin.models.ZZZElementType(element.id).name
        if isinstance(element, hakushin.zzz.CharacterProp)
        else element.name
    )
    return ZZZ_ELEMENT_EMOJIS[ZZZElement(name.title())]


def get_hsr_path_emoji(path: str) -> str:
    return HSR_PATH_EMOJIS[HSRPath(path.title())]


def get_artifact_pos_emoji(artifact_pos: str) -> str:
    return ARTIFACT_POS_EMOJIS[artifact_pos.lower()]


def get_relic_pos_emoji(relic_pos: str) -> str:
    return RELIC_POS_EMOJIS[relic_pos.lower()]
