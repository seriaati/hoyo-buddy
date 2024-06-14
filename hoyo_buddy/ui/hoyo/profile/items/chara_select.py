from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Final, TypeAlias

import enka

from hoyo_buddy.bot.translator import LevelStr, LocaleStr
from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji
from hoyo_buddy.enums import CharacterType
from hoyo_buddy.models import HoyolabHSRCharacter
from hoyo_buddy.ui.components import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.bot.bot import Interaction

    from ..view import Character, ProfileView  # noqa: F401
    from .build_select import BuildSelect

Builds: TypeAlias = dict[str, list[enka.gi.Build]] | dict[str, list[enka.hsr.Build]]

DATA_TYPES: Final[dict[CharacterType, LocaleStr]] = {
    CharacterType.BUILD: LocaleStr(key="profile.character_select.enka_network.description"),
    CharacterType.LIVE: LocaleStr(key="profile.character_select.live_data.description"),
    CharacterType.CACHE: LocaleStr(key="profile.character_select.cached_data.description"),
}


def determine_chara_type(
    character_id: str,
    cache_extras: dict[str, dict[str, Any]],
    builds: Builds,
    hoyolab: bool,
) -> CharacterType:
    key = f"{character_id}-hoyolab" if hoyolab else character_id
    if key not in cache_extras or character_id in builds:
        return CharacterType.BUILD
    if cache_extras[key]["live"]:
        return CharacterType.LIVE
    return CharacterType.CACHE


class CharacterSelect(PaginatorSelect["ProfileView"]):
    def __init__(
        self,
        characters: Sequence[Character],
        cache_extras: dict[str, dict[str, Any]],
        builds: Builds,
    ) -> None:
        options: list[SelectOption] = []

        for character in characters:
            character_type = determine_chara_type(
                str(character.id), cache_extras, builds, isinstance(character, HoyolabHSRCharacter)
            )
            data_type = DATA_TYPES[character_type]

            if isinstance(character, enka.hsr.Character):
                description = LocaleStr(
                    key="profile.character_select.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolons_unlocked,
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element.value)
            elif isinstance(character, HoyolabHSRCharacter):
                description = LocaleStr(
                    key="profile.character_select.hoyolab.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolons_unlocked,
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element)
            else:
                description = LocaleStr(
                    key="profile.genshin.character_select.description",
                    level=character.level,
                    const=character.constellations_unlocked,
                    refine=character.weapon.refinement,
                    data_type=data_type,
                )
                emoji = get_gi_element_emoji(character.element.name)

            options.append(
                SelectOption(
                    label=LocaleStr(
                        custom_str="{name} ({level_str})",
                        translate=False,
                        name=character.name,
                        level_str=LevelStr(character.level),
                    ),
                    description=description,
                    value=str(character.id),
                    emoji=emoji,
                )
            )

        super().__init__(
            options,
            placeholder=LocaleStr(key="profile.character_select.placeholder"),
            custom_id="profile_character_select",
        )

    async def callback(self, i: Interaction) -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.character_id = self.values[0]
        character = self.view._get_character(self.view.character_id)
        self.view.character_type = determine_chara_type(
            self.view.character_id,
            self.view.cache_extras,
            self.view._builds,
            isinstance(character, HoyolabHSRCharacter),
        )

        # Enable the player info button
        player_btn = self.view.get_item("profile_player_info")
        player_btn.disabled = False

        # Enable the card settings button
        card_settings_btn = self.view.get_item("profile_card_settings")
        card_settings_btn.disabled = False

        # Enable the remove from cache button if the character is in the cache
        with contextlib.suppress(ValueError):
            # The button is not present in the view if view._account is None
            remove_from_cache_btn = self.view.get_item("profile_remove_from_cache")
            remove_from_cache_btn.disabled = self.view.character_type is not CharacterType.CACHE

        # Set builds
        builds = self.view._builds.get(self.view.character_id, [])
        if builds:
            self.view._build_id = builds[0].id
        build_select: BuildSelect = self.view.get_item("profile_build_select")
        build_select.set_options(builds)
        build_select.translate(self.view.locale, self.view.translator)

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
