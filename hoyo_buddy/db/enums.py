from enum import StrEnum
from typing import Dict, Union

import genshin

__all__ = ("Game", "GAME_CONVERTER", "GAME_THUMBNAILS")


class Game(StrEnum):
    GENSHIN = "Genshin Impact"
    STARRAIL = "Honkai: Star Rail"
    HONKAI = "Honkai Impact 3rd"


GAME_CONVERTER: Dict[Union[Game, genshin.Game], Union[Game, genshin.Game]] = {
    Game.GENSHIN: genshin.Game.GENSHIN,
    Game.STARRAIL: genshin.Game.STARRAIL,
    Game.HONKAI: genshin.Game.HONKAI,
    genshin.Game.GENSHIN: Game.GENSHIN,
    genshin.Game.STARRAIL: Game.STARRAIL,
    genshin.Game.HONKAI: Game.HONKAI,
}

GAME_THUMBNAILS: Dict[Union[Game, genshin.Game], str] = {
    Game.GENSHIN: "https://i.imgur.com/t0Y5tYb.png",
    Game.STARRAIL: "https://i.imgur.com/nokmKT3.png",
    Game.HONKAI: "https://i.imgur.com/8yJ4nWP.png",
    genshin.Game.GENSHIN: "https://i.imgur.com/t0Y5tYb.png",
    genshin.Game.STARRAIL: "https://i.imgur.com/nokmKT3.png",
    genshin.Game.HONKAI: "https://i.imgur.com/8yJ4nWP.png",
}
