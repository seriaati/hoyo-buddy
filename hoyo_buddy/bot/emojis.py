from typing import Union

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

GENSHIN_IMPACT = "<:genshin_impact:1025630733068423169>"
HONKAI_STAR_RAIL = "<:honkai_star_rail:1105806784117088336>"
HONKAI_IMPACT_3RD = "<:honkai_impact:1106034318666637415>"


def get_game_emoji(game: Union[genshin.Game, Game]) -> str:
    if game is genshin.Game.GENSHIN or game is Game.GENSHIN:
        return GENSHIN_IMPACT
    if game is genshin.Game.HONKAI or game is Game.HONKAI:
        return HONKAI_IMPACT_3RD
    if game is genshin.Game.STARRAIL or game is Game.STARRAIL:
        return HONKAI_STAR_RAIL
    raise ValueError(f"Invalid game: {game}")
