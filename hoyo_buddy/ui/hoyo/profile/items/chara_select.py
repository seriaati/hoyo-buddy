from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from enka.hsr import Character as HSRCharacter

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji
from hoyo_buddy.ui.components import PaginatorSelect, SelectOption

from .....models import HoyolabHSRCharacter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import Character, ProfileView  # noqa: F401
    from .build_select import BuildSelect


class CharacterSelect(PaginatorSelect["ProfileView"]):
    def __init__(
        self,
        characters: Sequence[Character],
        cache_extras: dict[str, dict[str, Any]],
    ) -> None:
        options: list[SelectOption] = []

        for character in characters:
            if str(character.id) not in cache_extras:
                data_type = LocaleStr(
                    "Enka Network build", key="profile.character_select.enka_network.description"
                )
            else:
                data_type = (
                    LocaleStr(
                        "Real-time data", key="profile.character_select.live_data.description"
                    )
                    if cache_extras[str(character.id)]["live"]
                    else LocaleStr(
                        "Cached data", key="profile.character_select.cached_data.description"
                    )
                )

            if isinstance(character, HSRCharacter):
                description = LocaleStr(
                    "Lv.{level} | E{eidolons}S{superposition} | {data_type} | From in-game showcase",
                    key="profile.character_select.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolons_unlocked,
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element.value)
            elif isinstance(character, HoyolabHSRCharacter):
                description = LocaleStr(
                    "Lv.{level} | E{eidolons}S{superposition} | {data_type} | From HoYoLAB",
                    key="profile.character_select.hoyolab.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolons_unlocked,
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element)
            else:
                description = LocaleStr(
                    "Lv.{level} | C{const}R{refine} | {data_type}",
                    key="profile.genshin.character_select.description",
                    level=character.level,
                    const=character.constellations_unlocked,
                    refine=character.weapon.refinement,
                    data_type=data_type,
                )
                emoji = get_gi_element_emoji(character.element.name)

            options.append(
                SelectOption(
                    label=character.name,
                    description=description,
                    value=str(character.id),
                    emoji=emoji,
                )
            )

        super().__init__(
            options,
            placeholder=LocaleStr("Select a character", key="profile.character_select.placeholder"),
            custom_id="profile_character_select",
        )

    async def callback(self, i: INTERACTION) -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.character_id = self.values[0]

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
            remove_from_cache_btn.disabled = (
                self.view.character_id in self.view.live_data_character_ids
            )

        # Set builds
        build_select: BuildSelect = self.view.get_item("profile_build_select")
        build_select.set_options(self.view._builds.get(self.view.character_id, []))

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
