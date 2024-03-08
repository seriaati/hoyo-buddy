from enum import IntEnum, StrEnum

import genshin

__all__ = ("Game", "GAME_CONVERTER", "GAME_THUMBNAILS")


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"


class NotesNotifyType(IntEnum):
    RESIN = 1
    """Genshin Impact Resin"""
    REALM_CURRENCY = 2
    """Genshin Impact Realm Currency (serenitea pot)"""
    TB_POWER = 3
    """Star Rail Trailblaze Power"""
    GI_EXPED = 4
    """Genshin Impact Expedition"""
    HSR_EXPED = 5
    """Star Rail Expedition"""
    PT = 6
    """Genshin Impact Parametric Transformer"""
    # GI_DAILY = 7
    # """Genshin Impact Daily Commissions"""
    # HSR_DAILY = 8
    # """Star Rail Daily Training"""
    # RESIN_DISCOUNT = 9
    # """Genshin Impact Resin Discount"""
    # ECHO_OF_WAR = 10
    # """Star Rail Echo of War"""
    RESERVED_TB_POWER = 11
    """Star Rail Reserved Trailblaze Power"""


GAME_CONVERTER: dict[Game | genshin.Game, Game | genshin.Game] = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
    genshin.Game.GENSHIN: Game.GENSHIN,
    genshin.Game.STARRAIL: Game.STARRAIL,
    genshin.Game.HONKAI: Game.HONKAI,
}

GAME_THUMBNAILS: dict[Game | genshin.Game, str] = {
    Game.GENSHIN: "https://i.imgur.com/t0Y5tYb.png",
    Game.STARRAIL: "https://i.imgur.com/nokmKT3.png",
    Game.HONKAI: "https://i.imgur.com/8yJ4nWP.png",
    genshin.Game.GENSHIN: "https://i.imgur.com/t0Y5tYb.png",
    genshin.Game.STARRAIL: "https://i.imgur.com/nokmKT3.png",
    genshin.Game.HONKAI: "https://i.imgur.com/8yJ4nWP.png",
}
