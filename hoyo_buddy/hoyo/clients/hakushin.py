from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

import hakushin
import hakushin.clients
import yatta

from ...constants import TRAILBLAZER_IDS, YATTA_PATH_TO_HSR_PATH, contains_traveler_id
from ...embeds import DefaultEmbed
from ...emojis import get_hsr_path_emoji, get_zzz_element_emoji
from ...l10n import LevelStr, LocaleStr, Translator

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

__all__ = ("HakushinTranslator",)

SKILL_TYPE_ICONS: Final[dict[hakushin.enums.ZZZSkillType, str]] = {
    hakushin.enums.ZZZSkillType.BASIC: "https://api.hakush.in/zzz/UI/Icon_Normal.webp",
    hakushin.enums.ZZZSkillType.SPECIAL: "https://api.hakush.in/zzz/UI/Icon_SpecialReady.webp",
    hakushin.enums.ZZZSkillType.ASSIST: "https://api.hakush.in/zzz/UI/Icon_Switch.webp",
    hakushin.enums.ZZZSkillType.DODGE: "https://api.hakush.in/zzz/UI/Icon_Evade.webp",
    hakushin.enums.ZZZSkillType.CHAIN: "https://api.hakush.in/zzz/UI/Icon_UltimateReady.webp",
}
STAR_NUMS: Final[dict[Literal["S", "A", "B"], int]] = {"S": 5, "A": 4, "B": 3}


class ItemCategory(StrEnum):
    GI_CHARACTERS = "gi_characters"
    HSR_CHARACTERS = "hsr_characters"
    WEAPONS = "weapons"
    LIGHT_CONES = "light_cones"
    ARTIFACT_SETS = "artifact_sets"
    RELICS = "relics"


class ZZZItemCategory(StrEnum):
    AGENTS = "cat_zzz_agents"
    BANGBOOS = "cat_zzz_bangboos"
    W_ENGINES = "cat_zzz_w_engines"
    DRIVE_DISCS = "cat_zzz_drive_discs"


class HakushinTranslator:
    def __init__(self, locale: Locale, translator: Translator) -> None:
        self._locale = locale
        self._translator = translator

    def get_character_embed(
        self,
        character: hakushin.gi.CharacterDetail | hakushin.hsr.CharacterDetail,
        level: int,
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        stat_values = (
            hakushin.utils.calc_gi_chara_upgrade_stat_values(character, level, True)
            if isinstance(character, hakushin.gi.CharacterDetail)
            else hakushin.utils.calc_hsr_chara_upgrade_stat_values(character, level, True)
        )

        formatted_stat_values = hakushin.utils.format_stat_values(stat_values)
        named_stat_values = hakushin.utils.replace_fight_prop_with_name(formatted_stat_values, manual_weapon)

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
                value=hakushin.utils.get_skill_attributes(level_upgrade.attributes, level_upgrade.parameters),
            )
            embed.set_thumbnail(url=level_upgrade.icon)
        else:
            level_upgrade = skill.level_info[str(level)]
            if skill.description is not None:
                embed.add_field(
                    name=LocaleStr(key="skill_attributes_embed_field_name", level=level),
                    value=hakushin.utils.replace_placeholders(skill.description, level_upgrade.parameters),
                )
        return embed

    def get_character_passive_embed(self, passive: hakushin.gi.CharacterPassive) -> DefaultEmbed:
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=passive.name,
            description=hakushin.utils.replace_layout(passive.description).replace("#", ""),
        )
        embed.set_thumbnail(url=passive.icon)
        return embed

    def get_character_const_embed(self, const: hakushin.gi.CharacterConstellation) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator, title=const.name, description=const.description)
        embed.set_thumbnail(url=const.icon)
        return embed

    def get_character_eidolon_embed(self, eidolon: hakushin.hsr.Eidolon) -> DefaultEmbed:
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=eidolon.name,
            description=hakushin.utils.replace_placeholders(eidolon.description, eidolon.parameters),
        )
        embed.set_thumbnail(url=eidolon.image)
        return embed

    def get_weapon_embed(
        self, weapon: hakushin.gi.WeaponDetail, level: int, refinement: int, manual_weapon: dict[str, str]
    ) -> DefaultEmbed:
        stat_values = hakushin.utils.calc_weapon_upgrade_stat_values(weapon, level, True)
        formatted_stat_values = hakushin.utils.format_stat_values(stat_values)
        named_stat_values = hakushin.utils.replace_fight_prop_with_name(formatted_stat_values, manual_weapon)

        level_str = self._translator.translate(LevelStr(level), self._locale)
        embed = DefaultEmbed(
            self._locale, self._translator, title=f"{weapon.name} ({level_str})", description=f"{weapon.rarity}★\n"
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
        lang: hakushin.Language,
    ) -> DefaultEmbed:
        level_str = self._translator.translate(LevelStr(level), self._locale)
        embed = DefaultEmbed(self._locale, self._translator, title=f"{light_cone.name} ({level_str})")
        lc_path = yatta.PathType(light_cone.path.value)
        path_emoji = get_hsr_path_emoji(YATTA_PATH_TO_HSR_PATH[lc_path].value)
        path_name = hakushin.constants.HSR_PATH_NAMES[lang][light_cone.path]
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
                light_cone.superimpose_info.description, light_cone.superimpose_info.parameters[str(superimpose)]
            ),
            inline=False,
        )
        embed.set_thumbnail(url=light_cone.image)

        return embed

    def get_relic_embed(self, relic_set: hakushin.hsr.RelicSetDetail, relic: hakushin.hsr.Relic) -> DefaultEmbed:
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

        embed = DefaultEmbed(self._locale, self._translator, title=relic.name, description=description)
        embed.set_author(name=relic_set.name, icon_url=relic_set.icon)
        embed.set_footer(text=relic.description)
        embed.set_thumbnail(url=relic.icon)

        return embed

    def get_artifact_embed(
        self, artifact_set: hakushin.gi.ArtifactSetDetail, artifact: hakushin.gi.Artifact
    ) -> DefaultEmbed:
        description = self._translator.translate(
            LocaleStr(
                bonus_2=artifact_set.set_effect.two_piece.description, key="artifact_set_two_piece_embed_description"
            ),
            self._locale,
        )
        if artifact_set.set_effect.four_piece is not None:
            four_piece = LocaleStr(
                bonus_4=artifact_set.set_effect.four_piece.description, key="artifact_set_four_piece_embed_description"
            )
            description += "\n" + self._translator.translate(four_piece, self._locale)

        embed = DefaultEmbed(self._locale, self._translator, title=artifact.name, description=description)
        embed.set_author(name=artifact_set.set_effect.two_piece.name, icon_url=artifact_set.icon)
        embed.set_footer(text=artifact.description)
        embed.set_thumbnail(url=artifact.icon)
        return embed

    def translate_mc_names(
        self,
        characters: Sequence[hakushin.gi.Character] | Sequence[hakushin.hsr.Character],
        *,
        gender_symbol: bool = False,
    ) -> Sequence[hakushin.gi.Character] | Sequence[hakushin.hsr.Character]:
        """Translate the name of the main characters in GI and HSR."""
        for character in characters:
            if isinstance(character, hakushin.gi.Character) and contains_traveler_id(str(character.id)):
                character.name = self._translator.get_traveler_name(
                    character, self._locale, gender_symbol=gender_symbol
                )
            elif isinstance(character, hakushin.hsr.Character) and character.id in TRAILBLAZER_IDS:
                character.name = self._translator.get_trailblazer_name(
                    character, self._locale, gender_symbol=gender_symbol
                )

        return characters

    def get_agent_info_embed(self, agent: hakushin.zzz.CharacterDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self._locale,
            self._translator,
            title=agent.name,
            description=LocaleStr(
                key="zzz_search.agent_info",
                rarity=agent.rarity or "?",
                specialty=agent.specialty.name,
                atk_type=agent.attack_type.name,
                faction=agent.faction.name,
                element=f"{get_zzz_element_emoji(agent.element)} {agent.element.name}",
            ),
        )
        embed.set_image(url=agent.image)
        return embed

    def get_agent_skill_embed(
        self, skill: hakushin.zzz.CharacterSkill, agent: hakushin.zzz.CharacterDetail
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator)
        for desc in skill.descriptions:
            if desc.description is None:
                continue
            embed.add_field(name=desc.name, value=desc.description, inline=False)
        embed.set_thumbnail(url=SKILL_TYPE_ICONS[skill.type])
        embed.set_author(name=agent.name, icon_url=agent.icon)
        return embed

    def get_agent_core_embed(
        self, cores: hakushin.zzz.CharacterCoreSkill, agent: hakushin.zzz.CharacterDetail
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator)
        core = cores.levels[1]
        embed.add_field(name=core.names[0], value=core.descriptions[0], inline=False)
        embed.add_field(name=core.names[1], value=core.descriptions[1], inline=False)
        embed.set_thumbnail(url="https://api.hakush.in/zzz/UI/Icon_CoreSkill.webp")
        embed.set_author(name=agent.name, icon_url=agent.icon)
        return embed

    def get_agent_cinema_embed(
        self, cinema: hakushin.zzz.MindscapeCinema, agent_id: int, index: int, agent: hakushin.zzz.CharacterDetail
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator, title=cinema.name, description=cinema.description)
        embed.set_footer(text=cinema.description2)

        phases = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 5: 3}
        url = f"https://api.hakush.in/zzz/UI/Mindscape_{agent_id}_{phases[index]}.webp"
        embed.set_image(url=url)
        embed.set_author(name=agent.name, icon_url=agent.icon)
        return embed

    def get_bangboo_embed(self, bangboo: hakushin.zzz.BangbooDetail) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator, title=bangboo.name)
        embed.description = "★" * STAR_NUMS[bangboo.rarity]
        for skill_id, skill_info in bangboo.skills.items():
            skill = skill_info.get("1")
            if skill is None:
                continue
            embed.add_field(name=f"{skill_id}. {skill.name}", value=skill.description, inline=False)
        embed.set_thumbnail(url=bangboo.icon)
        embed.set_footer(text=bangboo.description)
        return embed

    def get_engine_embed(self, engine: hakushin.zzz.WeaponDetail, refinement: str) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator, title=engine.name)
        embed.description = ""
        if engine.rarity is not None:
            embed.description = "★" * STAR_NUMS[engine.rarity]
        embed.description += f"\n{engine.description}\n\n{engine.description2}"

        effect = engine.refinements[refinement]
        embed.add_field(name=f"{effect.name} ({refinement})", value=effect.description)
        embed.set_footer(text=engine.short_description)
        embed.set_thumbnail(url=engine.icon)
        return embed

    def get_disc_embed(self, disc: hakushin.zzz.DriveDiscDetail) -> DefaultEmbed:
        embed = DefaultEmbed(self._locale, self._translator, title=disc.name)

        two_piece = LocaleStr(key="artifact_set_two_piece_embed_description", bonus_2=disc.two_piece_effect).translate(
            self._translator, self._locale
        )
        four_piece = LocaleStr(
            key="artifact_set_four_piece_embed_description", bonus_4=disc.four_piece_effect
        ).translate(self._translator, self._locale)
        embed.description = f"{two_piece}\n{four_piece}"

        embed.set_thumbnail(url=disc.icon)
        return embed


class HakushinZZZClient(hakushin.clients.ZZZClient):
    async def fetch_item_rarity(self, item_id: str) -> int:
        agents = await self.fetch_characters()
        engines = await self.fetch_weapons()
        items = agents + engines

        for item in items:
            if str(item.id) == item_id and item.rarity is not None:
                return STAR_NUMS[item.rarity]

        return 0
