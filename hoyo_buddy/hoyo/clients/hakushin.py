from __future__ import annotations

from typing import TYPE_CHECKING

from hakushin.clients import HSRClient
from seria.utils import create_bullet_list, shorten

from hoyo_buddy.constants import locale_to_hakushin_lang
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import get_hsr_element_emoji
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr, translator

__all__ = ("HakushinHSRClient",)

if TYPE_CHECKING:
    from collections.abc import Mapping

    import aiohttp
    from hakushin.models import hsr

MAX_ENEMY_SKILLS = 10
ENEMY_SKILL_DESC_MAX_LENGTH = 250


class HakushinHSRClient(HSRClient):
    def __init__(
        self, locale: Locale = Locale.american_english, session: aiohttp.ClientSession | None = None
    ) -> None:
        super().__init__(lang=locale_to_hakushin_lang(locale), session=session)
        self.locale = locale

    def _add_enemy_skill_fields(
        self, embed: DefaultEmbed, monster: hsr.MonsterDetail
    ) -> DefaultEmbed:
        skills = [skill for skill in monster.skills if skill.name and skill.desc]
        for skill in skills[:MAX_ENEMY_SKILLS]:
            emoji = get_hsr_element_emoji(skill.damage_type.value) if skill.damage_type else None
            name = f"{emoji} {skill.name}" if emoji is not None else skill.name
            embed.add_field(
                name=name, value=shorten(skill.desc, ENEMY_SKILL_DESC_MAX_LENGTH), inline=False
            )
        return embed

    def _add_enemy_rewards_field(
        self, embed: DefaultEmbed, monster: hsr.MonsterDetail, item_names: Mapping[int, str]
    ) -> DefaultEmbed:
        drop = max(monster.drops, key=lambda drop: drop.world_level, default=None)
        if drop is None or (not drop.item_ids and not drop.avatar_exp_reward):
            return embed

        rewards: list[str] = []
        if drop.avatar_exp_reward:
            rewards.append(
                translator.translate(
                    LocaleStr(key="enemy_rewards_character_exp", exp=drop.avatar_exp_reward),
                    self.locale,
                )
            )
        rewards.extend(item_names.get(item_id, str(item_id)) for item_id in drop.item_ids)

        return embed.add_field(
            name=LocaleStr(key="enemy_rewards_field_name", level=drop.world_level),
            value=create_bullet_list(rewards),
            inline=False,
        )

    def get_enemy_embed(
        self, monster: hsr.MonsterDetail, item_names: Mapping[int, str] | None = None
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale, title=monster.name, description=monster.description or None
        )

        weaknesses = list(
            dict.fromkeys(
                element
                for monster_type in monster.monster_types
                for element in monster_type.stance_weak_list
            )
        )
        if weaknesses:
            embed.add_field(
                name=LocaleStr(key="enemy_weaknesses_field_name"),
                value=" ".join(get_hsr_element_emoji(element.value) for element in weaknesses),
                inline=False,
            )

        monster_type = next(iter(monster.monster_types), None)
        if monster_type is not None and monster_type.damage_type_resistances:
            embed.add_field(
                name=LocaleStr(key="enemy_resistances_field_name"),
                value="\n".join(
                    f"{get_hsr_element_emoji(res.element.value)} {res.value:.0%}"
                    for res in monster_type.damage_type_resistances
                ),
                inline=False,
            )

        self._add_enemy_skill_fields(embed, monster)
        self._add_enemy_rewards_field(embed, monster, item_names or {})

        embed.set_thumbnail(url=monster.icon)
        return embed
