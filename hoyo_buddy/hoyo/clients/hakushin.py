from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Literal, overload

import discord
import hakushin
import yatta

from ...bot.translator import LevelStr, LocaleStr, Translator
from ...constants import LOCALE_TO_HAKUSHIN_LANG, YATTA_PATH_TO_HSR_PATH, contains_traveler_id
from ...embeds import DefaultEmbed
from ...emojis import get_hsr_path_emoji

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

        level_str = self._translator.translate(LevelStr(level), self._locale)
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{character.name} ({level_str})",
            description=f"{character.rarity}★\n",
        )

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
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
            description=hakushin.utils.replace_layout(skill.description).replace("#", "")
            if isinstance(skill, hakushin.gi.CharacterSkill)
            else None,
        )

        if isinstance(skill, hakushin.gi.CharacterSkill):
            level_upgrade = skill.upgrade_info[str(level - 1)]
            embed.add_field(
                name=LocaleStr(key="skill_attributes_embed_field_name", level=level),
                value=hakushin.utils.get_skill_attributes(
                    level_upgrade.attributes, level_upgrade.parameters
                ),
            )
            embed.set_thumbnail(url=level_upgrade.icon)
        else:
            level_upgrade = skill.level_info[str(level)]
            embed.add_field(
                name=LocaleStr(key="skill_attributes_embed_field_name", level=level),
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

        level_str = self._translator.translate(LevelStr(level), self._locale)
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{weapon.name} ({level_str})",
            description=f"{weapon.rarity}★\n",
        )

        if weapon.refinments:
            embed.add_field(
                name=LocaleStr(r=refinement, key="refinement_indicator"),
                value=weapon.refinments[str(refinement)].description,
                inline=False,
            )

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
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
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        level_str = self._translator.translate(LevelStr(level), self._locale)
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{light_cone.name} ({level_str})",
        )
        lc_path = yatta.PathType(light_cone.path.value)
        path_emoji = get_hsr_path_emoji(YATTA_PATH_TO_HSR_PATH[lc_path].value)
        path_name = hakushin.constants.HSR_PATH_NAMES[self.lang][light_cone.path]
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=f"{light_cone.name} ({level_str})",
            description=f"{'★' * light_cone.rarity}\n{path_emoji} {path_name}",
        )

        result = hakushin.utils.calc_light_cone_upgrade_stat_values(light_cone, level, True)
        result = hakushin.utils.format_stat_values(result)
        result = hakushin.utils.replace_fight_prop_with_name(result, manual_weapon)

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in result.items()),
            inline=False,
        )
        embed.add_field(
            name=f"{light_cone.superimpose_info.name} ({superimpose})",
            value=hakushin.utils.replace_placeholders(
                light_cone.superimpose_info.description,
                light_cone.superimpose_info.parameters[str(superimpose)],
            ),
            inline=False,
        )
        embed.set_thumbnail(url=light_cone.image)

        return embed

    def get_relic_embed(
        self, relic_set: hakushin.hsr.RelicSetDetail, relic: hakushin.hsr.Relic
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        set_effects = relic_set.set_effects
        description = self._translator.translate(
            LocaleStr(
                bonus_2=hakushin.utils.replace_placeholders(
                    set_effects.two_piece.description, set_effects.two_piece.parameters
                ),
                key="artifact_set_two_piece_embed_description",
            ),
            self._locale,
        )
        if set_effects.four_piece is not None:
            four_piece = LocaleStr(
                bonus_4=hakushin.utils.replace_placeholders(
                    set_effects.four_piece.description, set_effects.four_piece.parameters
                ),
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + self._translator.translate(four_piece, self._locale)

        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=relic.name,
            description=description,
        )
        embed.set_author(name=relic_set.name, icon_url=relic_set.icon)
        embed.set_footer(text=relic.description)
        embed.set_thumbnail(url=relic.icon)

        return embed

    def get_artifact_embed(
        self, artifact_set: hakushin.gi.ArtifactSetDetail, artifact: hakushin.gi.Artifact
    ) -> DefaultEmbed:
        self._check_translator()
        assert self._translator is not None

        description = self._translator.translate(
            LocaleStr(
                bonus_2=artifact_set.set_effect.two_piece.description,
                key="artifact_set_two_piece_embed_description",
            ),
            self._locale,
        )
        if artifact_set.set_effect.four_piece is not None:
            four_piece = LocaleStr(
                bonus_4=artifact_set.set_effect.four_piece.description,
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + self._translator.translate(four_piece, self._locale)

        embed = DefaultEmbed(
            self._locale, self._translator, title=artifact.name, description=description
        )
        embed.set_author(name=artifact_set.set_effect.two_piece.name, icon_url=artifact_set.icon)
        embed.set_footer(text=artifact.description)
        embed.set_thumbnail(url=artifact.icon)
        return embed

    @overload
    async def fetch_characters(
        self, game: Literal[hakushin.Game.GI], *, traveler_gender_symbol: bool = False
    ) -> list[hakushin.gi.Character]: ...
    @overload
    async def fetch_characters(
        self, game: Literal[hakushin.Game.HSR], *, traveler_gender_symbol: bool = False
    ) -> list[hakushin.hsr.Character]: ...
    async def fetch_characters(
        self,
        game: Literal[hakushin.Game.GI, hakushin.Game.HSR],
        *,
        traveler_gender_symbol: bool = False,
    ) -> list[hakushin.gi.Character] | list[hakushin.hsr.Character]:
        self._check_translator()
        assert self._translator is not None

        characters = await super().fetch_characters(game)
        if game is hakushin.Game.HSR:
            return characters

        for character in characters:
            assert isinstance(character, hakushin.gi.Character)
            if contains_traveler_id(str(character.id)):
                character.name = self._translator.get_traveler_name(
                    character, self._locale, gender_symbol=traveler_gender_symbol
                )

        return characters
