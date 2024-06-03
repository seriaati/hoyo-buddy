from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

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
        character: hakushin.gi.CharacterDetail | hakushin.hsr.CharacterDetail,
        level: int,
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        stat_values = (
            hakushin.utils.calc_gi_chara_upgrade_stat_values(character, level, True)
            if isinstance(character, hakushin.gi.CharacterDetail)
            else hakushin.utils.calc_hsr_chara_upgrade_stat_values(character, level, True)
        )

        formatted_stat_values = hakushin.utils.format_stat_values(stat_values)
        named_stat_values = hakushin.utils.replace_fight_prop_with_name(
            formatted_stat_values, manual_weapon
        )

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
            description=f"{character.rarity}★\n",
        )

        embed.add_field(
            name=LocaleStr("Stats", key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
        )
        embed.set_footer(text=character.description)
        embed.set_thumbnail(url=character.icon)
        embed.set_image(url=character.gacha_art)

        return embed

    def get_character_skill_embed(
        self, skill: hakushin.gi.CharacterSkill | hakushin.hsr.Skill, level: int
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=skill.name,
            description=hakushin.utils.replace_layout(skill.description).replace("#", ""),
        )

        if isinstance(skill, hakushin.gi.CharacterSkill):
            level_upgrade = skill.upgrade_info[str(level - 1)]
            embed.add_field(
                name=LocaleStr(
                    "Skill Attributes (Lv.{level})",
                    key="skill_attributes_embed_field_name",
                    level=level,
                ),
                value=hakushin.utils.get_skill_attributes(
                    level_upgrade.attributes, level_upgrade.parameters
                ),
            )
            embed.set_thumbnail(url=level_upgrade.icon)
        else:
            level_upgrade = skill.level_info[str(level)]
            embed.add_field(
                name=LocaleStr(
                    "Skill Attributes (Lv.{level})",
                    key="skill_attributes_embed_field_name",
                    level=level,
                ),
                value=hakushin.utils.replace_placeholders(
                    skill.description, level_upgrade.parameters
                ),
            )
        return embed

    def get_character_passive_embed(self, passive: hakushin.gi.CharacterPassive) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=passive.name,
            description=hakushin.utils.replace_layout(passive.description).replace("#", ""),
        )
        embed.set_thumbnail(url=passive.icon)
        return embed

    def get_character_const_embed(self, const: hakushin.gi.CharacterConstellation) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=const.name,
            description=const.description,
        )
        embed.set_thumbnail(url=const.icon)
        return embed

    def get_character_eidolon_embed(self, eidolon: hakushin.hsr.Eidolon) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=eidolon.name,
            description=hakushin.utils.replace_placeholders(
                eidolon.description, eidolon.parameters
            ),
        )
        embed.set_thumbnail(url=eidolon.image)
        return embed

    def get_weapon_embed(
        self,
        weapon: hakushin.gi.WeaponDetail,
        level: int,
        refinement: int,
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        stat_values = hakushin.utils.calc_weapon_upgrade_stat_values(weapon, level, True)
        formatted_stat_values = hakushin.utils.format_stat_values(stat_values)
        named_stat_values = hakushin.utils.replace_fight_prop_with_name(
            formatted_stat_values, manual_weapon
        )

        level_str = LocaleStr(
            "Lv.{level}",
            key="level_str",
            level=level,
        ).translate(self._translator, self._locale)
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{weapon.name} ({level_str})",
            description=f"{weapon.rarity}★\n",
        )

        if weapon.refinments:
            embed.add_field(
                name=LocaleStr("Refinement {r}", r=refinement, key="refinement_indicator"),
                value=weapon.refinments[str(refinement)].description,
                inline=False,
            )

        embed.add_field(
            name=LocaleStr("Stats", key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
            inline=False,
        )

        embed.set_thumbnail(url=weapon.icon)
        embed.set_footer(text=weapon.description)
        return embed

    def get_light_cone_embed(
        self,
        light_cone: hakushin.hsr.LightConeDetail,
        level: int,
        superimpose: int,
        manual_avatar: dict[str, Any],
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

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
            title=f"{light_cone.name} ({level_str})",
            description=light_cone.description,
        )

        result = hakushin.utils.calc_light_cone_upgrade_stat_values(light_cone, level, True)

        named_stat_values: dict[str, Any] = {}
        for key, value in result:
            named_stat = manual_avatar[key]["name"]
            named_stat_values[named_stat] = int(value[level - 1])

        embed.add_field(
            name=LocaleStr("Stats", key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
            inline=False,
        )
        embed.add_field(
            name=light_cone.superimpose_info.name,
            value=hakushin.utils.replace_placeholders(
                light_cone.superimpose_info.description,
                light_cone.superimpose_info.parameters[str(superimpose)],
            ),
            inline=False,
        )
        embed.set_thumbnail(url=light_cone.icon)
        embed.set_footer(text=light_cone.description)

        return embed
