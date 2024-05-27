from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import discord
import hakushin

from ...constants import LOCALE_TO_HAKUSHIN_LANG

if TYPE_CHECKING:
    import aiohttp


class ItemCategory(StrEnum):
    GI_CHARACTERS = "gi_characters"
    HSR_CHARACTERS = "hsr_characters"
    WEAPONS = "weapons"
    LIGHT_CONES = "light_cones"
    ARTIFACT_SETS = "artifact_sets"
    RELICS = "relics"


class HakushinAPI(hakushin.HakushinAPI):
    def __init__(
        self,
        locale: discord.Locale = discord.Locale.american_english,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(LOCALE_TO_HAKUSHIN_LANG.get(locale, hakushin.Language.EN), session=session)
