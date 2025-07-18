from __future__ import annotations

import re
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import discord.utils as dutils
import yatta
from seria.utils import create_bullet_list
from yatta import Language

from hoyo_buddy.constants import LOCALE_TO_YATTA_LANG, TRAILBLAZER_IDS, YATTA_PATH_TO_HSR_PATH
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import get_hsr_element_emoji, get_hsr_path_emoji
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LevelStr, LocaleStr, translator
from hoyo_buddy.utils.misc import shorten_preserving_newlines

__all__ = ("ItemCategory", "YattaAPIClient")

if TYPE_CHECKING:
    import aiohttp


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
        self, locale: Locale = Locale.american_english, session: aiohttp.ClientSession | None = None
    ) -> None:
        super().__init__(lang=LOCALE_TO_YATTA_LANG.get(locale, Language.EN), session=session)
        self.locale = locale

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
        self, c: yatta.CharacterDetail, level: int, manual_avatar: dict[str, Any]
    ) -> DefaultEmbed:
        level_str = translator.translate(LevelStr(level), self.locale)
        embed = DefaultEmbed(
            self.locale,
            title=f"{c.name} ({level_str})",
            description=LocaleStr(
                key="yatta_character_embed_description",
                rarity="★" * c.rarity,
                element=f"{get_hsr_element_emoji(c.types.combat_type.id)} {c.types.combat_type.name}",
                path=c.types.path_type.name,
                world=c.info.faction,
            ),
        )

        upgrade: yatta.CharacterUpgrade | None = None

        for upgrade in c.upgrades:
            if level < upgrade.max_level:
                break

        if upgrade is None:
            upgrade = c.upgrades[-1]

        stat_values: dict[str, str] = {}

        for key, value in upgrade.skill_base.items():
            add = upgrade.skill_add.get(key.replace("Base", "Add"), 0)
            final_value = value + add * (level - 1)
            key_ = self._convert_upgrade_stat_key(key)
            stat_name = manual_avatar[key_]["name"]
            if stat_name is None:
                continue

            if key in {"criticalChance", "criticalDamage"}:
                stat_values[stat_name] = f"{final_value:.1%}"
            else:
                stat_values[stat_name] = str(int(final_value))

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in stat_values.items()),
        )
        embed.set_footer(text=c.info.description)
        embed.set_thumbnail(url=c.round_icon)
        embed.set_image(url=c.large_icon)

        return embed

    def get_character_main_skill_embed(
        self, skill: yatta.SkillListSkill, level: int
    ) -> DefaultEmbed:
        level_str = translator.translate(LevelStr(level), self.locale)

        embed = DefaultEmbed(
            self.locale,
            title=f"{skill.type}: {skill.name} ({level_str})",
            description=self._process_description_params(
                skill.description, skill.params, param_index=level - 1
            )
            if skill.description
            else None,
        )

        energy_generation = dutils.get(skill.skill_points, type="base")
        energy_need = dutils.get(skill.skill_points, type="need")

        energy_value_strs: list[str] = []
        if energy_generation and energy_generation.value:
            energy_value_strs.append(
                translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_energy_generation_field_value",
                        energy_generation=energy_generation.value,
                    ),
                    self.locale,
                )
            )
        if energy_need and energy_need.value:
            energy_value_strs.append(
                translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_energy_need_field_value",
                        energy_need=energy_need.value,
                    ),
                    self.locale,
                )
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
                translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_single_weakness_break_field_value",
                        single_weakness_break=single_weakness_break.value,
                    ),
                    self.locale,
                )
            )
        if spread_weakness_break and spread_weakness_break.value:
            weakness_break_value_strs.append(
                translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_spread_weakness_break_field_value",
                        spread_weakness_break=spread_weakness_break.value,
                    ),
                    self.locale,
                )
            )
        if aoe_weakness_break and aoe_weakness_break.value:
            weakness_break_value_strs.append(
                translator.translate(
                    LocaleStr(
                        key="yatta_character_skill_aoe_weakness_break_field_value",
                        aoe_weakness_break=aoe_weakness_break.value,
                    ),
                    self.locale,
                )
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
        embed = DefaultEmbed(
            self.locale,
            title=skill.name,
            description=self._process_description_params(skill.description, skill.params)
            if skill.description
            else None,
        )
        embed.set_thumbnail(url=skill.icon)

        return embed

    def get_character_eidolon_embed(self, eidolon: yatta.CharacterEidolon) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=eidolon.name,
            description=self._process_description_params(eidolon.description, eidolon.params),
        )
        embed.set_thumbnail(url=eidolon.icon)

        return embed

    def get_character_story_embed(self, story: yatta.CharacterStory) -> tuple[DefaultEmbed, str]:
        return (
            DefaultEmbed(
                self.locale,
                title=story.title,
                description=shorten_preserving_newlines(story.text, 300),
            ),
            story.text,
        )

    def get_character_voice_embed(
        self, voice: yatta.CharacterVoice, character_id: int
    ) -> DefaultEmbed:
        description = f"{voice.text}"
        if voice.audio is not None:
            voice_str = " ".join(
                f"[{lang}](https://api.yatta.top/hsr/assets/Audio/{lang}/{character_id}/{voice.audio}.ogg)"
                for lang in AUDIO_LANGUAGES
            )
            description += f"\n\n{voice_str}"

        return DefaultEmbed(self.locale, title=voice.title, description=description)

    def get_item_embed(self, item: yatta.ItemDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale, title=f"{item.name}\n{'★' * item.rarity}", description=item.description
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
        self, lc: yatta.LightConeDetail, level: int, superimpose: int, manual_avatar: dict[str, Any]
    ) -> DefaultEmbed:
        level_str = translator.translate(LevelStr(level), self.locale)

        lc_path = yatta.PathType(lc.type.id)
        path_emoji = get_hsr_path_emoji(YATTA_PATH_TO_HSR_PATH[lc_path].value)
        embed = DefaultEmbed(
            self.locale,
            title=f"{lc.name} ({level_str})",
            description=f"{'★' * lc.rarity}\n{path_emoji} {lc.type.name}",
        )

        upgrade: yatta.LightConeUpgrade | None = None

        for upgrade in lc.upgrades:
            if level < upgrade.max_level:
                break

        if upgrade is None:
            upgrade = lc.upgrades[-1]

        stat_values: dict[str, float] = {}

        for key, value in upgrade.skill_base.items():
            add = upgrade.skill_add.get(key.replace("Base", "Add"), 0)
            final_value = value + add * (level - 1)
            key_ = self._convert_upgrade_stat_key(key)
            stat_name = manual_avatar[key_]["name"]
            stat_values[stat_name] = int(final_value)

        embed.add_field(
            name=LocaleStr(key="stats_embed_field_name"),
            value="\n".join(f"{k}: {v}" for k, v in stat_values.items()),
            inline=False,
        )
        embed.add_field(
            name=f"{lc.skill.name} ({superimpose})",
            value=self._process_description_params(
                lc.skill.description, lc.skill.params, param_index=superimpose - 1
            ),
            inline=False,
        )
        embed.set_thumbnail(url=lc.large_icon)

        return embed

    def get_book_series_embed(
        self, book: yatta.BookDetail, series: yatta.BookSeries
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=series.name, description=series.story)
        embed.set_author(name=book.name, icon_url=book.icon)
        embed.set_footer(text=book.description)

        return embed

    def get_relic_embed(self, relic_set: yatta.RelicSetDetail, relic: yatta.Relic) -> DefaultEmbed:
        set_effects = relic_set.set_effects
        description = translator.translate(
            LocaleStr(
                bonus_2=self._process_description_params(
                    set_effects.two_piece.description, set_effects.two_piece.params
                ),
                key="artifact_set_two_piece_embed_description",
            ),
            self.locale,
        )
        if set_effects.four_piece is not None:
            four_piece = LocaleStr(
                bonus_4=self._process_description_params(
                    set_effects.four_piece.description, set_effects.four_piece.params
                ),
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + translator.translate(four_piece, self.locale)

        embed = DefaultEmbed(self.locale, title=relic.name, description=description)
        embed.set_author(name=relic_set.name, icon_url=relic_set.icon)
        embed.set_footer(text=relic.description)
        embed.set_thumbnail(url=relic.icon)

        return embed

    async def fetch_characters(
        self, *, use_cache: bool = True, trailblazer_gender_symbol: bool = False
    ) -> list[yatta.models.Character]:
        characters = await super().fetch_characters(use_cache)

        for character in characters:
            if character.id in TRAILBLAZER_IDS:
                character.name = translator.get_trailblazer_name(
                    character, self.locale, gender_symbol=trailblazer_gender_symbol
                )

        return characters

    async def fetch_item_rarity(self, item_id: str) -> int:
        characters = await super().fetch_characters()
        light_cones = await self.fetch_light_cones()
        items = characters + light_cones

        for item in items:
            if str(item.id) == item_id:
                return item.rarity

        msg = f"Item with ID {item_id!r} not found."
        raise ValueError(msg)
