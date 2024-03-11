from genshin import Game

from .enums import Game as GameEnum

RESIN_ICON = "https://api.ambr.top/assets/UI/UI_ItemIcon_210.png"
TBP_ICON = "https://api.yatta.top/hsr/assets/UI/item/11.png"
RTBP_ICON = "https://api.yatta.top/hsr/assets/UI/item/12.png"
PT_ICON = "https://api.ambr.top/assets/UI/UI_ItemIcon_220021.png"
COMMISSION_ICON = "https://i.imgur.com/x73cn2G.png"
REALM_CURRENCY_ICON = "https://i.imgur.com/eAJ0RFr.png"

GI_ICON = "https://i.imgur.com/QqqrBOg.png"
HSR_ICON = "https://i.imgur.com/jHyDVSv.png"
HONKAI_ICON = "https://i.imgur.com/9ueIKNO.png"


def get_game_icon(game: Game | GameEnum) -> str:
    match game:
        case Game.GENSHIN | GameEnum.GENSHIN:
            return GI_ICON
        case Game.STARRAIL | GameEnum.STARRAIL:
            return HSR_ICON
        case Game.HONKAI | GameEnum.HONKAI:
            return HONKAI_ICON
        case _:
            msg = f"Invalid game: {game!r}"
            raise ValueError(msg)
