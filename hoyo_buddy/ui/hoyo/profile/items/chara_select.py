from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Final

import enka
from genshin.models import ZZZPartialAgent

from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji, get_zzz_element_emoji
from hoyo_buddy.enums import CharacterType, Game
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.models import HoyolabHSRCharacter
from hoyo_buddy.ui import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.types import Builds, Interaction

    from ..view import Character, ProfileView  # noqa: F401
    from .build_select import BuildSelect


DATA_TYPES: Final[dict[CharacterType, LocaleStr]] = {
    CharacterType.BUILD: LocaleStr(key="profile.character_select.enka_network.description"),
    CharacterType.LIVE: LocaleStr(key="profile.character_select.live_data.description"),
    CharacterType.CACHE: LocaleStr(key="profile.character_select.cached_data.description"),
}
MAX_VALUES: Final[dict[Game, int]] = {
    Game.GENSHIN: 4,
    Game.STARRAIL: 4,
    Game.ZZZ: 3,
}


def determine_chara_type(
    character_id: str,
    *,
    cache_extras: dict[str, dict[str, Any]],
    builds: Builds,
    is_hoyolab: bool,
) -> CharacterType:
    key = f"{character_id}-hoyolab" if is_hoyolab else character_id
    chara_builds = builds.get(character_id, [])
    if key not in cache_extras or (chara_builds and not any(build.live for build in chara_builds)):
        return CharacterType.BUILD
    if cache_extras[key]["live"]:
        return CharacterType.LIVE
    return CharacterType.CACHE


class CharacterSelect(PaginatorSelect["ProfileView"]):
    def __init__(
        self,
        game: Game,
        characters: Sequence[Character],
        cache_extras: dict[str, dict[str, Any]],
        builds: Builds,
    ) -> None:
        options: list[SelectOption] = []

        for character in characters:
            character_type = determine_chara_type(
                str(character.id),
                cache_extras=cache_extras,
                builds=builds,
                is_hoyolab=isinstance(character, HoyolabHSRCharacter | ZZZPartialAgent),
            )
            data_type = DATA_TYPES[character_type]

            if isinstance(character, enka.hsr.Character):
                description = LocaleStr(
                    key="profile.character_select.description",
                    s=character.light_cone.superimpose if character.light_cone is not None else 0,
                    e=character.eidolons_unlocked,
                    d=data_type,
                )
                emoji = get_hsr_element_emoji(character.element.value)
            elif isinstance(character, HoyolabHSRCharacter):
                description = LocaleStr(
                    key="profile.character_select.hoyolab.description",
                    s=character.light_cone.superimpose if character.light_cone is not None else 0,
                    e=character.eidolons_unlocked,
                    d=data_type,
                )
                emoji = get_hsr_element_emoji(character.element)
            elif isinstance(character, enka.gi.Character):
                description = LocaleStr(
                    key="profile.genshin.character_select.description",
                    c=character.constellations_unlocked,
                    r=character.weapon.refinement,
                    d=data_type,
                )
                emoji = get_gi_element_emoji(character.element.name)
            else:  # ZZZPartialAgent
                description = LocaleStr(
                    key="profile.zzz_hoyolab.character_select.description", m=character.rank
                )
                emoji = get_zzz_element_emoji(character.element.name)

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
            max_values=MAX_VALUES[game],
        )

    async def callback(self, i: Interaction) -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.character_id = self.values[0]
        character = self.view.characters[self.view.character_id]
        self.view.character_type = determine_chara_type(
            self.view.character_id,
            cache_extras=self.view.cache_extras,
            builds=self.view._builds,
            is_hoyolab=isinstance(character, HoyolabHSRCharacter),
        )

        # Enable the player info button
        player_btn = self.view.get_item("profile_player_info")
        player_btn.disabled = False

        # Enable the card settings button
        card_settings_btn = self.view.get_item("profile_card_settings")
        card_settings_btn.disabled = self.view.game is Game.ZZZ

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
