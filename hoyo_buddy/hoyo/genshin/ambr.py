import re
from enum import StrEnum
from typing import Any, Dict, List, Tuple, Union

import ambr
from ambr.client import Language
from discord import Locale

from ...bot.translator import Translator
from ...bot.translator import locale_str as _T
from ...embeds import DefaultEmbed

LOCALE_TO_LANG: Dict[Locale, Language] = {
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

PERCENTAGE_FIGHT_PROPS: Tuple[str, ...] = (
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
    ACHIEVEMENTS = "Achievements"
    TCG = "TCG"


class AmbrAPIClient(ambr.AmbrAPI):
    def __init__(self, locale: Locale, translator: Translator) -> None:
        super().__init__(LOCALE_TO_LANG.get(locale, Language.EN))
        self.locale = locale
        self.translator = translator

    async def __aenter__(self) -> "AmbrAPIClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return await super().close()

    @staticmethod
    def _replace_talent_params(
        description: List[str], params: List[Union[int, float]]
    ) -> List[str]:
        def repl(match: re.Match[str]) -> str:
            index = int(match.group(1)) - 1  # Convert to zero-based index
            format_spec = match.group(2)
            value = params[index]
            if format_spec == "F1P":
                value *= 100  # Multiply by 100 if format specifier is 'F1P'
            return str(value)

        return [re.sub(r"\{param(\d+):F1(P)?\}", repl, s) for s in description]

    @staticmethod
    def _calculate_upgrade_stat_values(
        upgrade_data: Union[ambr.CharacterUpgrade, ambr.WeaponUpgrade],
        curve_data: Dict[str, Dict[str, Dict[str, float]]],
        level: int,
        ascended: bool,
    ) -> Dict[str, float]:
        result: Dict[str, float] = {}

        for stat in upgrade_data.base_stats:
            if stat.prop_type is None:
                continue
            result[stat.prop_type] = (
                stat.init_value * curve_data[str(level)]["curveInfos"][stat.growth_type]
            )

        for promote in upgrade_data.promotes:
            if promote.add_stats is None:
                continue
            if level >= promote.unlock_max_level:
                if level == promote.unlock_max_level and ascended:
                    for stat in promote.add_stats:
                        result[stat.id] += stat.value
                elif level > promote.unlock_max_level:
                    for stat in promote.add_stats:
                        if stat.value != 0:
                            result[stat.id] += stat.value

        return result

    @staticmethod
    def _format_stat_values(stat_values: Dict[str, float]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for fight_prop, value in stat_values.items():
            if fight_prop in PERCENTAGE_FIGHT_PROPS:
                value = round(value, 1)
                result[fight_prop] = f"{value}%"
            else:
                value = round(value)
                result[fight_prop] = str(value)
        return result

    @staticmethod
    def _replace_fight_prop_with_name(
        stat_values: Dict[str, Any], manual_weapon: Dict[str, str]
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for fight_prop, value in stat_values.items():
            fight_prop_name = manual_weapon.get(fight_prop, fight_prop)
            result[fight_prop_name] = value
        return result

    def get_character_embed(
        self,
        character: ambr.CharacterDetail,
        level: int,
        avatar_curve: Dict[str, Dict[str, Dict[str, float]]],
        manual_weapon: Dict[str, str],
    ) -> DefaultEmbed:
        stat_values = self._calculate_upgrade_stat_values(
            character.upgrade, avatar_curve, level, True
        )
        formatted_stat_values = self._format_stat_values(stat_values)
        named_stat_values = self._replace_fight_prop_with_name(
            formatted_stat_values, manual_weapon
        )

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=character.name,
            description=_T(
                (
                    "{rarity}★ {element}\n"
                    "Birthday: {birthday}\n"
                    "Constellation: {constellation}\n"
                    "Affiliation: {affiliation}\n"
                ),
                key="character_embed_description",
                rarity=character.rarity,
                element=_T(character.element.name, warn_no_key=False),
                birthday=f"{character.birthday.month}/{character.birthday.day}",
                constellation=character.info.constellation,
                affiliation=character.info.native,
            ),
        )
        embed.add_field(
            name=_T(
                "Stats (Lv. {level})",
                key="character_embed_stats_field_name",
                level=level,
            ),
            value="\n".join(f"{k}: {v}" for k, v in named_stat_values.items()),
        )
        embed.set_footer(text=character.info.detail)
        embed.set_thumbnail(url=character.icon)
        return embed

    def get_character_talent_embed(
        self, talent: ambr.Talent, level: int
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=talent.name,
            description=talent.description,
        )
        if talent.upgrades:
            level_upgrade = talent.upgrades[level - 1]
            embed.add_field(
                name=_T(
                    "Skill Attributes (Lv. {level})",
                    key="skill_attributes_embed_field_name",
                    level=level,
                ),
                value="\n".join(
                    self._replace_talent_params(
                        level_upgrade.description, level_upgrade.params
                    )
                ),
            )
        embed.set_thumbnail(url=talent.icon)
        return embed

    def get_character_constellation_embed(
        self, constellation: ambr.Constellation
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=constellation.name,
            description=constellation.description,
        )
        embed.set_thumbnail(url=constellation.icon)
        return embed

    def get_weapon_embed(
        self,
        weapon: ambr.WeaponDetail,
        level: int,
        refinement: int,
        ascended: bool,
        weapon_curve: Dict[str, Dict[str, Dict[str, float]]],
        manual_weapon: Dict[str, str],
    ) -> DefaultEmbed:
        stat_values = self._calculate_upgrade_stat_values(
            weapon.upgrade, weapon_curve, level, ascended
        )
        main_stat = weapon.upgrade.base_stats[0]
        if main_stat.prop_type is None:
            raise AssertionError("Weapon has no main stat")
        main_stat_name = manual_weapon[main_stat.prop_type]
        main_stat_value = stat_values[main_stat.prop_type]

        sub_stat = weapon.upgrade.base_stats[1]
        sub_stat_name = (
            manual_weapon[sub_stat.prop_type] if sub_stat.prop_type else None
        )
        sub_stat_value = stat_values[sub_stat.prop_type] if sub_stat.prop_type else None

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=_T("{weapon_name} (Lv. {lv})", weapon_name=weapon.name, lv=level),
            description=f"{weapon.rarity}★ {weapon.type}\n{main_stat_name}: {main_stat_value}",
        )

        if sub_stat_name and sub_stat_value:
            if embed.description is None:
                raise AssertionError("Embed description is None")
            embed.description += f"\n{sub_stat_name}: {sub_stat_value}"

        if weapon.affix:
            embed.add_field(
                name=_T("Refinement {r}", r=refinement),
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
        embed.set_image(url=namecard.icon)
        return embed

    def get_artifact_set_embed(
        self, artifact_set: ambr.ArtifactSetDetail
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=artifact_set.name,
            description=_T(
                "2-Pieces: {bonus_2}\n4-Pieces: {bonus_4}",
                bonus_2=artifact_set.affix_list[0].effect,
                bonus_4=artifact_set.affix_list[1].effect,
                key="artifact_set_embed_description",
            ),
        )
        return embed

    def get_artifact_embed(self, artifact: ambr.Artifact) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=artifact.name,
            description=artifact.description,
        )
        embed.set_thumbnail(url=artifact.icon)
        return embed
