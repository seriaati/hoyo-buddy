import re
from collections import defaultdict
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import ambr
import discord.utils as dutils
from ambr.client import Language
from discord import Locale

from ...bot.constants import WEEKDAYS
from ...bot.emojis import COMFORT_ICON, DICE_EMOJIS, LOAD_ICON, get_element_emoji
from ...bot.translator import LocaleStr, Translator
from ...embeds import DefaultEmbed
from ...utils import create_bullet_list, shorten

if TYPE_CHECKING:
    from types import TracebackType

LOCALE_TO_LANG: dict[Locale, Language] = {
    Locale.taiwan_chinese: Language.CHT,
    Locale.chinese: Language.CHS,
    Locale.german: Language.DE,
    Locale.american_english: Language.EN,
    Locale.spain_spanish: Language.ES,
    Locale.french: Language.FR,
    Locale.indonesian: Language.ID,
    Locale.japanese: Language.JP,
    Locale.korean: Language.KR,
    Locale.brazil_portuguese: Language.PT,
    Locale.russian: Language.RU,
    Locale.thai: Language.TH,
    Locale.vietnamese: Language.VI,
    Locale.italian: Language.IT,
    Locale.turkish: Language.TR,
}

PERCENTAGE_FIGHT_PROPS = (
    "FIGHT_PROP_HP_PERCENT",
    "FIGHT_PROP_ATTACK_PERCENT",
    "FIGHT_PROP_DEFENSE_PERCENT",
    "FIGHT_PROP_SPEED_PERCENT",
    "FIGHT_PROP_CRITICAL",
    "FIGHT_PROP_CRITICAL_HURT",
    "FIGHT_PROP_CHARGE_EFFICIENCY",
    "FIGHT_PROP_ADD_HURT",
    "FIGHT_PROP_HEAL_ADD",
    "FIGHT_PROP_HEALED_ADD",
    "FIGHT_PROP_FIRE_ADD_HURT",
    "FIGHT_PROP_WATER_ADD_HURT",
    "FIGHT_PROP_GRASS_ADD_HURT",
    "FIGHT_PROP_ELEC_ADD_HURT",
    "FIGHT_PROP_ICE_ADD_HURT",
    "FIGHT_PROP_WIND_ADD_HURT",
    "FIGHT_PROP_PHYSICAL_ADD_HURT",
    "FIGHT_PROP_ROCK_ADD_HURT",
    "FIGHT_PROP_SKILL_CD_MINUS_RATIO",
    "FIGHT_PROP_ATTACK_PERCENT_A",
    "FIGHT_PROP_DEFENSE_PERCENT_A",
    "FIGHT_PROP_HP_PERCENT_A",
)

AUDIO_LANGUAGES = ("EN", "CHS", "JP", "KR")


class ItemCategory(StrEnum):
    CHARACTERS = "Characters"
    WEAPONS = "Weapons"
    ARTIFACT_SETS = "Artifact Sets"
    FOOD = "Food"
    MATERIALS = "Materials"
    FURNISHINGS = "Furnishings"
    FURNISHING_SETS = "Furnishing Sets"
    NAMECARDS = "Namecards"
    LIVING_BEINGS = "Living Beings"
    BOOKS = "Books"
    TCG = "TCG"


class AmbrAPIClient(ambr.AmbrAPI):
    def __init__(self, locale: Locale, translator: Translator) -> None:
        super().__init__(LOCALE_TO_LANG.get(locale, Language.EN))
        self.locale = locale
        self.translator = translator

    async def __aenter__(self) -> "AmbrAPIClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> None:
        return await super().close()

    @staticmethod
    def _format_num(digits: int, calculation: int | float) -> str:
        return f"{calculation:.{digits}f}"

    @staticmethod
    def _calculate_upgrade_stat_values(
        upgrade_data: ambr.CharacterUpgrade | ambr.WeaponUpgrade,
        curve_data: dict[str, dict[str, dict[str, float]]],
        level: int,
        ascended: bool,
    ) -> dict[str, float]:
        result: defaultdict[str, float] = defaultdict(float)

        for stat in upgrade_data.base_stats:
            if stat.prop_type is None:
                continue
            result[stat.prop_type] = (
                stat.init_value * curve_data[str(level)]["curveInfos"][stat.growth_type]
            )

        for promote in reversed(upgrade_data.promotes):
            if promote.add_stats is None:
                continue
            if (level == promote.unlock_max_level and ascended) or level > promote.unlock_max_level:
                for stat in promote.add_stats:
                    if stat.value != 0:
                        result[stat.id] += stat.value
                        if stat.id in {
                            "FIGHT_PROP_CRITICAL_HURT",
                            "FIGHT_PROP_CRITICAL",
                        }:
                            result[stat.id] += 0.5
                break

        return result

    @staticmethod
    def _format_stat_values(stat_values: dict[str, float]) -> dict[str, str]:
        result: dict[str, str] = {}
        for fight_prop, value in stat_values.items():
            if fight_prop in PERCENTAGE_FIGHT_PROPS:
                result[fight_prop] = f"{round(value * 100, 1)}%"
            else:
                result[fight_prop] = str(round(value))
        return result

    @staticmethod
    def _replace_fight_prop_with_name(
        stat_values: dict[str, Any], manual_weapon: dict[str, str]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for fight_prop, value in stat_values.items():
            fight_prop_name = manual_weapon.get(fight_prop, fight_prop)
            result[fight_prop_name] = value
        return result

    @staticmethod
    def _format_layout(text: str) -> str:
        if "LAYOUT" in text:
            brackets = re.findall(r"{LAYOUT.*?}", text)
            word_to_replace = re.findall(r"{LAYOUT.*?#(.*?)}", brackets[0])[0]
            text = text.replace("".join(brackets), word_to_replace)
        return text

    def _get_params(self, text: str, param_list: list[int | float]) -> list[str]:
        params: list[str] = re.findall(r"{[^}]*}", text)

        for item in params:
            if "param" not in item:
                continue

            param_text = re.findall(r"{param(\d+):([^}]*)}", item)[0]
            param, value = param_text

            if value in {"F1P", "F2P"}:
                result = self._format_num(int(value[1]), param_list[int(param) - 1] * 100)
                text = re.sub(re.escape(item), f"{result}%", text)
            elif value in {"F1", "F2"}:
                result = self._format_num(int(value[1]), param_list[int(param) - 1])
                text = re.sub(re.escape(item), result, text)
            elif value == "P":
                result = self._format_num(0, param_list[int(param) - 1] * 100)
                text = re.sub(re.escape(item), f"{result}%", text)
            elif value == "I":
                result = int(param_list[int(param) - 1])
                text = re.sub(re.escape(item), str(round(result)), text)

        text = self._format_layout(text)
        text = text.replace("{NON_BREAK_SPACE}", "")
        text = text.replace("#", "")
        return text.split("|")

    def _get_skill_attributes(self, descriptions: list[str], params: list[int | float]) -> str:
        result = ""
        for desc in descriptions:
            try:
                k, v = self._get_params(desc, params)
            except ValueError:
                continue
            result += f"{k}: {v}\n"
        return result

    def get_character_embed(
        self,
        character: ambr.CharacterDetail,
        level: int,
        avatar_curve: dict[str, dict[str, dict[str, float]]],
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        stat_values = self._calculate_upgrade_stat_values(
            character.upgrade, avatar_curve, level, True
        )
        formatted_stat_values = self._format_stat_values(stat_values)
        named_stat_values = self._replace_fight_prop_with_name(formatted_stat_values, manual_weapon)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=character.name,
            description=LocaleStr(
                (
                    "{rarity}★ {element}\n"
                    "Birthday: {birthday}\n"
                    "Constellation: {constellation}\n"
                    "Affiliation: {affiliation}\n"
                ),
                key="character_embed_description",
                rarity=character.rarity,
                element=get_element_emoji(character.element.name),
                birthday=f"{character.birthday.month}/{character.birthday.day}",
                constellation=character.info.constellation,
                affiliation=character.info.native,
            ),
        )
        embed.add_field(
            name=LocaleStr(
                "Stats (Lv. {level})",
                key="character_embed_stats_field_name",
                level=level,
            ),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
        )
        embed.set_footer(text=character.info.detail)
        embed.set_thumbnail(url=character.icon)
        embed.set_image(url=character.gacha)
        return embed

    def get_character_talent_embed(self, talent: ambr.Talent, level: int) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=talent.name,
            description=self._format_layout(talent.description).replace("#", ""),
        )
        if talent.upgrades:
            try:
                level_upgrade = talent.upgrades[level - 1]
            except IndexError:
                level_upgrade = talent.upgrades[-1]
                level = level_upgrade.level
            embed.add_field(
                name=LocaleStr(
                    "Skill Attributes (Lv. {level})",
                    key="skill_attributes_embed_field_name",
                    level=level,
                ),
                value=self._get_skill_attributes(level_upgrade.description, level_upgrade.params),
            )
        embed.set_thumbnail(url=talent.icon)
        return embed

    def get_character_constellation_embed(self, constellation: ambr.Constellation) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=constellation.name,
            description=constellation.description,
        )
        embed.set_thumbnail(url=constellation.icon)
        return embed

    def get_character_story_embed(self, story: ambr.Story) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=story.title,
            description=story.text,
        )
        if story.tips:
            embed.set_footer(text=story.tips)
        return embed

    def get_character_quote_embed(self, quote: ambr.Quote, character_id: str) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=quote.title,
            description=f"{quote.text}\n\n"
            + " ".join(
                f"[{lang}](https://api.ambr.top/assets/Audio/{lang}/{character_id}/{quote.audio_id}.ogg)"
                for lang in AUDIO_LANGUAGES
            ),
        )
        if quote.tips:
            embed.set_footer(text=quote.tips)
        return embed

    def get_weapon_embed(
        self,
        weapon: ambr.WeaponDetail,
        level: int,
        refinement: int,
        weapon_curve: dict[str, dict[str, dict[str, float]]],
        manual_weapon: dict[str, str],
    ) -> DefaultEmbed:
        stat_values = self._calculate_upgrade_stat_values(weapon.upgrade, weapon_curve, level, True)
        main_stat = weapon.upgrade.base_stats[0]
        if main_stat.prop_type is None:
            msg = "Weapon has no main stat"
            raise AssertionError(msg)

        main_stat_name = manual_weapon[main_stat.prop_type]
        main_stat_value = stat_values[main_stat.prop_type]

        sub_stat = weapon.upgrade.base_stats[1]
        sub_stat_name = manual_weapon[sub_stat.prop_type] if sub_stat.prop_type else None
        sub_stat_value = stat_values[sub_stat.prop_type] if sub_stat.prop_type else None
        if sub_stat_value is not None and sub_stat.prop_type in PERCENTAGE_FIGHT_PROPS:
            sub_stat_value *= 100
            sub_stat_value = round(sub_stat_value, 1)
            sub_stat_value = f"{sub_stat_value}%"

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(
                "{weapon_name} (Lv. {lv})",
                weapon_name=weapon.name,
                lv=level,
                key="weapon_embed_title",
            ),
            description=(
                f"{weapon.rarity}★ {weapon.type}\n{main_stat_name}: {round(main_stat_value)}"
            ),
        )

        if sub_stat_name and sub_stat_value:
            if embed.description is None:
                msg = "Embed description is None"
                raise AssertionError(msg)
            embed.description += f"\n{sub_stat_name}: {sub_stat_value}"

        if weapon.affix:
            embed.add_field(
                name=LocaleStr("Refinement {r}", r=refinement, key="refinement_indicator"),
                value=weapon.affix.upgrades[refinement - 1].description,
            )
        embed.set_thumbnail(url=weapon.icon)
        embed.set_footer(text=weapon.description)
        return embed

    def get_namecard_embed(self, namecard: ambr.NamecardDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=namecard.name,
            description=namecard.description,
        )
        embed.set_thumbnail(url=namecard.icon)
        embed.set_image(url=namecard.picture)
        if namecard.source:
            embed.set_footer(text=namecard.source)
        return embed

    def get_artifact_embed(
        self, artifact_set: ambr.ArtifactSetDetail, artifact: ambr.Artifact
    ) -> DefaultEmbed:
        description = self.translator.translate(
            LocaleStr(
                "2-Pieces: {bonus_2}",
                bonus_2=artifact_set.affix_list[0].effect,
                key="artifact_set_two_piece_embed_description",
            ),
            self.locale,
        )
        if len(artifact_set.affix_list) == 2:
            four_piece = LocaleStr(
                "4-Pieces: {bonus_4}",
                bonus_4=artifact_set.affix_list[1].effect,
                key="artifact_set_four_piece_embed_description",
            )
            description += "\n" + self.translator.translate(four_piece, self.locale)

        embed = DefaultEmbed(
            self.locale, self.translator, title=artifact.name, description=description
        )
        embed.set_author(name=artifact_set.name, icon_url=artifact_set.icon)
        embed.set_footer(text=artifact.description)
        embed.set_thumbnail(url=artifact.icon)
        return embed

    def get_food_embed(self, food: ambr.FoodDetail) -> DefaultEmbed:
        description = create_bullet_list([s.name for s in food.sources])
        if isinstance(food.recipe, ambr.FoodRecipe):
            description += f"\n{create_bullet_list([e.description for e in food.recipe.effects])}"

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=food.name,
            description=description,
        )
        embed.set_thumbnail(url=food.icon)
        embed.set_footer(text=food.description)
        return embed

    def get_material_embed(self, material: ambr.MaterialDetail) -> DefaultEmbed:
        if material.sources:
            names: list[str] = []

            for source in material.sources:
                if source.days:
                    days_str = ", ".join(
                        [self.translator.translate(WEEKDAYS[d], self.locale) for d in source.days]
                    )
                    names.append(f"{source.name} ({days_str})")
                else:
                    names.append(source.name)

            description = create_bullet_list(names)
        else:
            description = material.description

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{material.name}\n{'★' * material.rarity}",
            description=description,
        )
        embed.set_thumbnail(url=material.icon)
        embed.set_author(name=material.type)

        if material.sources:
            embed.set_footer(text=material.description)

        return embed

    def get_furniture_embed(self, furniture: ambr.FurnitureDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=f"{furniture.name}\n{'★' * furniture.rarity}",
            description=LocaleStr(
                "{comfort_icon} Comfort: {comfort}\n"
                "{load_icon} Load: {load}\n"
                "Trust: {trust}\n"
                "Creation Time: {hour}h",
                key="furniture_embed_description",
                comfort_icon=COMFORT_ICON,
                load_icon=LOAD_ICON,
                comfort=furniture.comfort or 0,
                load=furniture.cost or 0,
                trust=furniture.recipe.exp if furniture.recipe else 0,
                hour=furniture.recipe.time // 3600 if furniture.recipe else 0,
            ),
        )

        # TODO: Add furniture ingredients
        embed.set_footer(text=furniture.description)
        embed.set_author(name=f"{furniture.types[-1]}/{furniture.categories[-1]}")
        embed.set_thumbnail(url=furniture.icon)
        return embed

    def get_furniture_set_embed(self, furniture_set: ambr.FurnitureSetDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=furniture_set.name,
            description=furniture_set.description,
        )

        # TODO: Add furniture set furnitures
        embed.set_author(name=f"{furniture_set.types[-1]}/{furniture_set.categories[-1]}")
        embed.set_image(url=furniture_set.icon)
        return embed

    def get_monster_embed(self, monster: ambr.MonsterDetail) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale, self.translator, title=monster.name, description=monster.description
        )
        if monster.special_name:
            embed.set_author(name=f"{monster.type}/{monster.special_name}")
        else:
            embed.set_author(name=monster.type)
        embed.set_thumbnail(url=monster.icon)
        return embed

    def get_volume_embed(
        self, book: ambr.BookDetail, volume: ambr.BookVolume, readable: str
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=volume.name,
            description=shorten(readable, 4096),
        )
        embed.set_author(name=book.name)
        embed.set_thumbnail(url=book.icon)
        embed.set_footer(text=volume.description)
        return embed

    def get_tcg_card_embed(self, card: ambr.TCGCardDetail) -> DefaultEmbed:
        energy = card.props.get("GCG_PROP_ENERGY", 0) if card.props else 0
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=card.name,
            description=DICE_EMOJIS["GCG_COST_ENERGY"] * energy,
        )
        embed.add_field(name=card.story_title, value=card.story_detail, inline=False)
        embed.set_author(name="/".join([t.name for t in card.tags]))
        embed.set_footer(text=card.source)
        embed.set_image(url=card.small_icon)
        return embed

    def get_tcg_card_dictionaries_embed(
        self, dictionaries: list[ambr.CardDictionary]
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator)
        for d in dictionaries:
            # skip talent related dictionaries
            if d.id[0] == "C":
                continue
            embed.add_field(name=d.name, value=d.description, inline=False)
        return embed

    def get_tcg_card_talent_embed(
        self, talent: ambr.CardTalent, dictionaries: list[ambr.CardDictionary]
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=talent.name,
            description=talent.description,
        )
        dice_str = "\n".join([f"{DICE_EMOJIS[d.type] * d.amount}" for d in talent.cost])

        if talent.sub_skills:
            for k in talent.sub_skills:
                dictionary = dutils.get(dictionaries, id=k)
                if dictionary:
                    embed.add_field(
                        name=dictionary.name, value=dictionary.description, inline=False
                    )

        embed.add_field(
            name=LocaleStr("Dice Cost", key="dice_cost_embed_field_name"), value=dice_str
        )

        embed.set_author(name="/".join([t.name for t in talent.tags]))
        embed.set_thumbnail(url=talent.icon)
        return embed
