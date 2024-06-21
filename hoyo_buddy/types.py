from typing import TypeAlias

import genshin

Challenge: TypeAlias = (
    genshin.models.StarRailChallenge
    | genshin.models.SpiralAbyss
    | genshin.models.StarRailPureFiction
    | genshin.models.StarRailAPCShadow
)
