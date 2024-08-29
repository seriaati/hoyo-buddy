from __future__ import annotations

import re
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import discord.utils as dutils
import yatta
from discord import Locale
from seria.utils import create_bullet_list
from yatta import Language

from ...constants import LOCALE_TO_YATTA_LANG, TRAILBLAZER_IDS, YATTA_PATH_TO_HSR_PATH
from ...embeds import DefaultEmbed
from ...emojis import get_hsr_element_emoji, get_hsr_path_emoji
from ...l10n import LevelStr, LocaleStr

__all__ = ("ItemCategory", "YattaAPIClient")

if TYPE_CHECKING:
    import aiohttp

    from ...l10n import Translator

KEY_DICT: dict[str, str] = {
    "hPBase": "maxHP",
    "attackBase": "attack",
    "defenceBase": "defence",
    "speedBase": "speed",
    "baseAggro": "aggro",
}
AUDIO_LANGUAGES = ("EN", "CN", "JP", "KR")


class ItemCategory(StrEnum):
    CHARACTERS = "Characters"
    LIGHT_CONES = "Light Cones"
    ITEMS = "Items"
    RELICS = "Relics"
    BOOKS = "Books"


class YattaAPIClient(yatta.YattaAPI):
    def __init__(
        self,
        locale: Locale = Locale.american_english,
        translator: Translator | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(lang=LOCALE_TO_YATTA_LANG.get(locale, Language.EN), session=session)
        self.locale = locale
        self.translator = translator

    def _process_description_params(
        self,
        description: str,
        params: dict[str, list[float | int]] | list[int | float] | None,
        *,
        param_index: int | None = None,
    ) -> str:
        if params is None:
            return description
        if isinstance(params, list):
            params_ = {str(i): [p] for i, p in enumerate(params, start=1)}
        else:
            params_ = params
            if param_index is not None:
                params_ = {k: [v[param_index]] for k, v in params_.items()}

        pattern = r"#(\d+)(?:\[(i|f\d+)\])(%?)"
        matches = re.findall(pattern, description)

        for match in matches:
            num = int(match[0])
            param = params_[str(num)]
            modifier = match[1]

            if match[2]:
                param = [p * 100 for p in param]

            if modifier == "i":
                param = [round(p) for p in param]
            elif modifier.startswith("f"):
                decimals = int(modifier[1:])
                param = [round(p, decimals) for p in param]

            replacement = str(param[0]) if len(set(param)) == 1 else "/".join(map(str, param))
            description = re.sub(rf"#{num}(?:\[{modifier}\])", replacement, description)

        return description

    def _calc_upgrade_stats(
        self, upgrades: list[yatta.models.LightConeUpgrade] | list[yatta.models.CharacterUpgrade],
    ) -> dict[str, Any]:
        result: list[dict[str, list[float]]] = []
        cost_count: dict[int, dict[str, int]] = {}
        full_upgrade: dict[str, int] = {}

        range_add = []
        for upgrade in upgrades:
            current_level = upgrade.level
            previous_max_level = 1 if current_level == 0 else upgrades[current_level - 1].max_level
            level_stats = {key: [upgrade.skill_base[key]] for key in upgrade.skill_base}
            range_add.append(upgrade.max_level)
            for key in upgrade.skill_add:
                key_replace = key.replace("Add", "Base")
                for _ in range(upgrade.max_level):
                    latest_stat = level_stats[key_replace][-1]
                    level_stats[key_replace].append(latest_stat + upgrade.skill_add[key])
                level_stats[key_replace] = level_stats[key_replace][
                    previous_max_level - 1 : upgrade.max_level
                ]

            for skill in upgrade.skill_base:
                if skill.replace("Base", "Add") not in upgrade.skill_add:
                    level_stats[skill].extend([0] * (upgrade.max_level - 1))

            if upgrade.cost_items:
                for cost_item in upgrade.cost_items:
                    key, value = str(cost_item.id), cost_item.amount
                    if key not in full_upgrade:
                        full_upgrade[key] = 0
                    full_upgrade[key] += value
                cost_count[1 if current_level == 0 else upgrade.max_level + 1] = full_upgrade.copy()
            result.append(level_stats)

        all_levels = {}
        for obj in result:
            for key, value in obj.items():
                all_levels[key] = all_levels.get(key, []) + value

        upgrade_max_level = upgrades[-1].max_level
        levels_map = [str(step) for step in range(1, upgrade_max_level + 1)]
        levels_map.extend([f"{step}+" for step in range(1, upgrade_max_level) if step in range_add])

        return {
            "levels": levels_map,
            "stats": all_levels,
            "cost": cost_count,
            "fullCost": full_upgrade,
        }

    def _convert_upgrade_stat_key(self, key: str) -> str:
        return KEY_DICT.get(key, key)

    async def fetch_element_char_counts(self) -> dict[str, int]:
        """Fetches the number of characters for each element, does not include beta characters and Trailblazer."""
        characters = await self.fetch_characters()
        result: defaultdict[str, int] = defaultdict(int)
        for character in characters:
            if character.beta or character.id in TRAILBLAZER_IDS:
                continue
            result[character.types.combat_type.value.lower()] += 1

        return dict(result)

    async def fetch_path_char_counts(self) -> dict[str, int]:
        """Fetches the number of characters for each path, does not include beta characters and Trailblazer."""
        characters = await self.fetch_characters()
        result: defaultdict[str, int] = defaultdict(int)
        for character in characters:
            if character.beta or character.id in TRAILBLAZER_IDS:
                continue
            converted_path = YATTA_PATH_TO_HSR_PATH[character.types.path_type]
            result[converted_path.name.lower()] += 1

        return dict(result)

    def get_character_details_embed(
        self, character: yatta.CharacterDetail, level: int, manual_avatar: dict[str, Any],
    ) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        level_str = self.translator.translate(LevelStr(level), self.locale)
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{character.name} ({level_str})",
            description=LocaleStr(
                key="yatta_character_embed_description",
                rarity="★" * character.rarity,
                element=f"{get_hsr_element_emoji(character.types.combat_type.id)} {character.types.combat_type.name}",
                path=character.types.path_type.name,
                world=character.info.faction,
            ),
        )

        result = self._calc_upgrade_stats(character.upgrades)
        named_stat_values: dict[str, Any] = {}

        for key, value in result["stats"].items():
            key_ = self._convert_upgrade_stat_key(key)
            named_stat = manual_avatar[key_]["name"]
            if named_stat is None:
                continue

            value_ = int(value[level - 1])
            value_ = int(value[0]) if value_ == 0 else value_
            if value_ == 0:
                continue

            named_stat_values[named_stat] = value_

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
        )
        embed.set_footer(text=character.info.description)
        embed.set_thumbnail(url=character.round_icon)
        embed.set_image(url=character.large_icon)

        return embed

    def get_character_main_skill_embed(
        self, skill: yatta.SkillListSkill, level: int,
    ) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        level_str = self.translator.translate(LevelStr(level), self.locale)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{skill.type}: {skill.name} ({level_str})",
            description=self._process_description_params(
                skill.description, skill.params, param_index=level - 1,
            )
            if skill.description
            else None,
        )

        energy_generation = dutils.get(skill.skill_points, type="base")
        energy_need = dutils.get(skill.skill_points, type="need")

        energy_value_strs: list[str] = []
        if energy_generation and energy_generation.value:
            energy_value_strs.append(
                self.translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_energy_generation_field_value",
                        energy_generation=energy_generation.value,
                    ),
                    self.locale,
                ),
            )
        if energy_need and energy_need.value:
            energy_value_strs.append(
                self.translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_energy_need_field_value",
                        energy_need=energy_need.value,
                    ),
                    self.locale,
                ),
            )
        if energy_value_strs:
            embed.add_field(
                name=LocaleStr(key="yatta_character_skill_energy_field_name"),
                value="/".join(energy_value_strs),
            )

        single_weakness_break = dutils.get(skill.weakness_break, type="one")
        spread_weakness_break = dutils.get(skill.weakness_break, type="spread")
        aoe_weakness_break = dutils.get(skill.weakness_break, type="all")

        weakness_break_value_strs: list[str] = []
        if single_weakness_break and single_weakness_break.value:
            weakness_break_value_strs.append(
                self.translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_single_weakness_break_field_value",
                        single_weakness_break=single_weakness_break.value,
                    ),
                    self.locale,
                ),
            )
        if spread_weakness_break and spread_weakness_break.value:
            weakness_break_value_strs.append(
                self.translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_spread_weakness_break_field_value",
                        spread_weakness_break=spread_weakness_break.value,
                    ),
                    self.locale,
                ),
            )
        if aoe_weakness_break and aoe_weakness_break.value:
            weakness_break_value_strs.append(
                self.translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_aoe_weakness_break_field_value",
                        aoe_weakness_break=aoe_weakness_break.value,
                    ),
                    self.locale,
                ),
            )
        if weakness_break_value_strs:
            embed.add_field(
                name=LocaleStr(key="yatta_character_skill_weakness_break_field_name"),
                value="/".join(weakness_break_value_strs),
            )

        embed.set_thumbnail(url=skill.icon)
        if skill.tag:
            embed.set_author(name=skill.tag)

        return embed

    def get_character_sub_skill_embed(self, skill: yatta.BaseSkill) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=skill.name,
            description=self._process_description_params(skill.description, skill.params)
            if skill.description
            else None,
        )
        embed.set_thumbnail(url=skill.icon)

        return embed

    def get_character_eidolon_embed(self, eidolon: yatta.CharacterEidolon) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=eidolon.name,
            description=self._process_description_params(eidolon.description, eidolon.params),
        )
        embed.set_thumbnail(url=eidolon.icon)

        return embed

    def get_character_story_embed(self, story: yatta.CharacterStory) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        return DefaultEmbed(
            self.locale,
            self.translator,
            title=story.title,
            description=story.text,
        )

    def get_character_voice_embed(
        self, voice: yatta.CharacterVoice, character_id: int,
    ) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        description = f"{voice.text}"
        if voice.audio is not None:
            voice_str = " ".join(
                f"[{lang}](https://api.yatta.top/hsr/assets/Audio/{lang}/{character_id}/{voice.audio}.ogg)"
                for lang in AUDIO_LANGUAGES
            )
            description += f"\n\n{voice_str}"

        return DefaultEmbed(
            self.locale, self.translator, title=voice.title, description=description,
        )

    def get_item_embed(self, item: yatta.ItemDetail) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{item.name}\n{'★' * item.rarity}",
            description=item.description,
        )
        if item.sources:
            embed.add_field(
                name=LocaleStr(key="yatta_item_sources_field_name"),
                value=create_bullet_list([source.description for source in item.sources]),
            )
        embed.set_footer(text=item.story)
        embed.set_author(name="/".join(item.tags))
        embed.set_thumbnail(url=item.icon)

        return embed

    def get_light_cone_embed(
        self,
        light_cone: yatta.LightConeDetail,
        level: int,
        superimpose: int,
        manual_avatar: dict[str, Any],
    ) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        level_str = self.translator.translate(LevelStr(level), self.locale)

        lc_path = yatta.PathType(light_cone.type.id)
        path_emoji = get_hsr_path_emoji(YATTA_PATH_TO_HSR_PATH[lc_path].value)
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{light_cone.name} ({level_str})",
            description=f"{'★' * light_cone.rarity}\n{path_emoji} {light_cone.type.name}",
        )

        result = self._calc_upgrade_stats(light_cone.upgrades)

        named_stat_values: dict[str, Any] = {}
        for key, value in result["stats"].items():
            key_ = self._convert_upgrade_stat_key(key)
            named_stat = manual_avatar[key_]["name"]
            named_stat_values[named_stat] = int(value[level - 1])

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
            inline=False,
        )
        embed.add_field(
            name=f"{light_cone.skill.name} ({superimpose})",
            value=self._process_description_params(
                light_cone.skill.description, light_cone.skill.params, param_index=superimpose - 1,
            ),
            inline=False,
        )
        embed.set_thumbnail(url=light_cone.large_icon)

        return embed

    def get_book_series_embed(
        self, book: yatta.BookDetail, series: yatta.BookSeries,
    ) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=series.name,
            description=series.story,
        )
        embed.set_author(name=book.name, icon_url=book.icon)
        embed.set_footer(text=book.description)

        return embed

    def get_relic_embed(self, relic_set: yatta.RelicSetDetail, relic: yatta.Relic) -> DefaultEmbed:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        set_effects = relic_set.set_effects
        description = self.translator.translate(
            LocaleStr(
                bonus_2=self._process_description_params(
                    set_effects.two_piece.description, set_effects.two_piece.params,
                ),
                key="artifact_set_two_piece_embed_description",
            ),
            self.locale,
        )
        if set_effects.four_piece is not None:
            four_piece = LocaleStr(
                bonus_4=self._process_description_params(
                    set_effects.four_piece.description, set_effects.four_piece.params,
                ),
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + self.translator.translate(four_piece, self.locale)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=relic.name,
            description=description,
        )
        embed.set_author(name=relic_set.name, icon_url=relic_set.icon)
        embed.set_footer(text=relic.description)
        embed.set_thumbnail(url=relic.icon)

        return embed

    async def fetch_characters(
        self, *, use_cache: bool = True, trailblazer_gender_symbol: bool = False,
    ) -> list[yatta.models.Character]:
        if self.translator is None:
            msg = "Translator is not set"
            raise RuntimeError(msg)

        characters = await super().fetch_characters(use_cache)

        for character in characters:
            if character.id in TRAILBLAZER_IDS:
                character.name = self.translator.get_trailblazer_name(
                    character, self.locale, gender_symbol=trailblazer_gender_symbol,
                )

        return characters
