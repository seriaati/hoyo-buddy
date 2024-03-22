import genshin

from .enums import Game, GenshinCity, GenshinElement, HSRElement, HSRPath

LOADING = "<a:loading_emoji:1106388708862738463>"
DELETE = "<:DELETE:1166012141833310248>"
EDIT = "<:EDIT:1166020688927260702>"
ADD = "<:ADD:1166153842816200804>"
BACK = "<:BACK:1166306958337396766>"
FORWARD = "<:FORWARD:1166687402337775646>"
REFRESH = "<:REFRESH:1166720923014021120>"
COOKIE = "<:COOKIE:1166729718431748176>"
PASSWORD = "<:PASSWORD:1166730162784710716>"
INFO = "<:INFO:1166743144889602190>"
SETTINGS = "<:SETTINGS:1169592948661432411>"
SMART_TOY = "<:SMART_TOY:1169597339162390528>"
FREE_CANCELLATION = "<:FREE_CANCELLATION:1169597369470427246>"
SEARCH = "<:search:1053142091682812054>"
BOOK_MULTIPLE = "<:bookmultiple:1067260453249618001>"
BELL_OUTLINE = "<:belloutline:1067642704814674062>"
LEFT = "<:left:982588994778972171>"
RIGHT = "<:right:982588993122238524>"
DOUBLE_LEFT = "<:double_left:982588991461281833>"
DOUBLE_RIGHT = "<:double_right:982588990223958047>"

GENSHIN_IMPACT = "<:genshin_impact:1025630733068423169>"
HONKAI_STAR_RAIL = "<:honkai_star_rail:1105806784117088336>"
HONKAI_IMPACT_3RD = "<:honkai_impact:1106034318666637415>"

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
}

ARTIFACT_POS_EMOJIS: dict[str, str] = {
    "flower": "<:Flower_of_Life:982167959717945374>",
    "plume": "<:Plume_of_Death:982167959915077643>",
    "sands": "<:Sands_of_Eon:982167959881547877>",
    "goblet": "<:Goblet_of_Eonothem:982167959835402240>",
    "circlet": "<:Circlet_of_Logos:982167959692787802>",
}
DICE_EMOJIS: dict[str, str] = {
    "GCG_COST_ENERGY": "<:UI_Gcg_DiceL_Energy:1054218252668108820>",
    "GCG_COST_DICE_VOID": "<:UI_Gcg_DiceL_Diff_Glow:1054218256870805565>",
    "GCG_COST_DICE_SAME": "<:UI_Gcg_DiceL_Any_Glow:1054218258737278976>",
    "GCG_COST_DICE_CRYO": "<:UI_Gcg_DiceL_Ice_Glow:1054218246619930644>",
    "GCG_COST_DICE_HYDRO": "<:UI_Gcg_DiceL_Water_Glow:1054218240487850115>",
    "GCG_COST_DICE_PYRO": "<:UI_Gcg_DiceL_Fire_Glow:1054218250747117689>",
    "GCG_COST_DICE_ELECTRO": "<:UI_Gcg_DiceL_Electric_Glow:1054218254903681098>",
    "GCG_COST_DICE_ANEMO": "<:UI_Gcg_DiceL_Wind_Glow:1054218238566879336>",
    "GCG_COST_DICE_GEO": "<:UI_Gcg_DiceL_Rock_Glow:1054218244656992286>",
    "GCG_COST_DICE_DENDRO": "<:UI_Gcg_DiceL_Grass_Glow:1054218248477999135>",
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

COMFORT_ICON = "<:comfort_icon:1045528772222394378>"
LOAD_ICON = "<:load_icon:1045528773992386650>"
PROJECT_AMBER = "<:PROJECT_AMBER:1191752455998930955>"

RESIN = "<:resin:1004648472995168326>"
REALM_CURRENCY = "<:realm:1004648474266062880>"
PT_EMOJI = "<:transformer:1004648470981902427>"

TRAILBLAZE_POWER = "<:trailblaze_power:1120556064509788160>"
RESERVED_TRAILBLAZE_POWER = "<:RESERVED_TRAILBLAZE_POWER:1215465874539028520>"


def get_game_emoji(game: genshin.Game | Game) -> str:
    if game is genshin.Game.GENSHIN or game is Game.GENSHIN:
        return GENSHIN_IMPACT
    if game is genshin.Game.HONKAI or game is Game.HONKAI:
        return HONKAI_IMPACT_3RD
    if game is genshin.Game.STARRAIL or game is Game.STARRAIL:
        return HONKAI_STAR_RAIL


def get_gi_element_emoji(element: str) -> str:
    return GENSHIN_ELEMENT_EMOJIS[GenshinElement(element.lower())]


def get_hsr_element_emoji(element: str) -> str:
    if element.lower() == "lightning":
        element = "thunder"
    return HSR_ELEMENT_EMOJIS[HSRElement(element.lower())]


def get_hsr_path_emoji(path: str) -> str:
    return HSR_PATH_EMOJIS[HSRPath(path.lower())]


def get_artifact_pos_emoji(artifact_pos: str) -> str:
    return ARTIFACT_POS_EMOJIS[artifact_pos.lower()]


def get_relic_pos_emoji(relic_pos: str) -> str:
    return RELIC_POS_EMOJIS[relic_pos.lower()]
