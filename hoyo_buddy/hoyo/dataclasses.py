from typing import TYPE_CHECKING

import mihomo
from attr import dataclass

from ..constants import MIHOMO_LANG_TO_LOCALE

if TYPE_CHECKING:
    import discord


@dataclass(kw_only=True)
class Reward:
    name: str
    amount: int
    index: int
    claimed: bool
    icon: str


class ExtendedCharacter(mihomo.models.Character):
    live: bool = False
    lang: str = "en"

    @property
    def locale(self) -> "discord.Locale":
        return MIHOMO_LANG_TO_LOCALE[mihomo.Language(self.lang)]


class ExtendedStarRailInfoParsed(mihomo.StarrailInfoParsed):
    characters: list[ExtendedCharacter]
