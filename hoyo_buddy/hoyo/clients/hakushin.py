from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import ambr
import discord
import hakushin

from ...bot.translator import LocaleStr, Translator
from ...constants import LOCALE_TO_HAKUSHIN_LANG
from ...embeds import DefaultEmbed

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
        translator: Translator | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(LOCALE_TO_HAKUSHIN_LANG.get(locale, hakushin.Language.EN), session=session)

        self._locale = locale
        self._translator = translator

    def _check_translator(self) -> None:
        if self._translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

    def get_character_embed(
        self,
        character: hakushin.gi.CharacterDetail,
        level: int,
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        stat_values = self._calculate_upgrade_stat_values(
            character.upgrade, avatar_curve, level, True
        )
        formatted_stat_values = self._format_stat_values(stat_values)
        named_stat_values = self._replace_fight_prop_with_name(formatted_stat_values, manual_weapon)

        level_str = self._translator.translate(
            LocaleStr(
                "Lv.{level}",
                key="level_str",
                level=level,
            ),
            self._locale,
        )
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{character.name} ({level_str})",
            description=LocaleStr(
                "{rarity}★\n",
                key="character_embed_description",
                rarity=character.rarity,
            ),
        )

        embed.add_field(
            name=LocaleStr("Stats", key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
        )
        embed.set_footer(text=character.description)
        embed.set_thumbnail(url=character.icon)
        embed.set_image(url=character.gacha_art)
        return embed
