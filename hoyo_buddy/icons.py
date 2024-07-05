from __future__ import annotations

from genshin import Game

from .enums import Game as GameEnum

RESIN_ICON = "https://api.ambr.top/assets/UI/UI_ItemIcon_210.png"
TBP_ICON = "https://api.yatta.top/hsr/assets/UI/item/11.png"
RTBP_ICON = "https://api.yatta.top/hsr/assets/UI/item/12.png"
PT_ICON = "https://api.ambr.top/assets/UI/UI_ItemIcon_220021.png"
COMMISSION_ICON = "https://i.imgur.com/x73cn2G.png"
REALM_CURRENCY_ICON = "https://i.imgur.com/eAJ0RFr.png"

GI_ICON = "https://iili.io/dKleQ4I.png"
HSR_ICON = "https://iili.io/dKlesBp.png"
HONKAI_ICON = "https://iili.io/dKleLEN.png"
ZZZ_ICON = "https://iili.io/dKlekrP.png"

LOADING_ICON = "https://i.imgur.com/5siJ799.gif"


def get_game_icon(game: Game | GameEnum) -> str:
    if game in {Game.GENSHIN, GameEnum.GENSHIN}:
        return GI_ICON
    if game in {Game.STARRAIL, GameEnum.STARRAIL}:
        return HSR_ICON
    if game in {Game.HONKAI, GameEnum.HONKAI}:
        return HONKAI_ICON
    if game in {Game.ZZZ, GameEnum.ZZZ}:
        return ZZZ_ICON

    msg = f"This game doesn't have an icon: {game}"
    raise ValueError(msg)
