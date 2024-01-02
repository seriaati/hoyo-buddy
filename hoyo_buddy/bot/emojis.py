import genshin

from ..db.enums import Game

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

GENSHIN_IMPACT = "<:genshin_impact:1025630733068423169>"
HONKAI_STAR_RAIL = "<:honkai_star_rail:1105806784117088336>"
HONKAI_IMPACT_3RD = "<:honkai_impact:1106034318666637415>"

ELEMENT_EMOJIS: dict[str, str] = {
    "pyro": "<:pyro:1189150911428317275>",
    "hydro": "<:hydro:1189150893875142726>",
    "cryo": "<:cryo:1189150960413573141>",
    "anemo": "<:anemo:1189150874916888636>",
    "dendro": "<:dendro:1189150946878562354>",
    "geo": "<:geo:1189150979657044012>",
    "electro": "<:electro:1189150927190495232>",
}
ARTIFACT_POS_EMOJIS: dict[str, str] = {
    "flower": "<:Flower_of_Life:982167959717945374>",
    "plume": "<:Plume_of_Death:982167959915077643>",
    "sands": "<:Sands_of_Eon:982167959881547877>",
    "goblet": "<:Goblet_of_Eonothem:982167959835402240>",
    "circlet": "<:Circlet_of_Logos:982167959692787802>",
}


def get_game_emoji(game: genshin.Game | Game) -> str:
    if game is genshin.Game.GENSHIN or game is Game.GENSHIN:
        return GENSHIN_IMPACT
    if game is genshin.Game.HONKAI or game is Game.HONKAI:
        return HONKAI_IMPACT_3RD
    if game is genshin.Game.STARRAIL or game is Game.STARRAIL:
        return HONKAI_STAR_RAIL
    msg = f"Invalid game: {game}"
    raise ValueError(msg)


def get_element_emoji(element: str) -> str:
    return ELEMENT_EMOJIS[element.lower()]


def get_artifact_pos_emoji(artifact_pos: str) -> str:
    return ARTIFACT_POS_EMOJIS[artifact_pos.lower()]
