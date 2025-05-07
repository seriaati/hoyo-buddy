from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import enka
from genshin.models import ZZZPartialAgent

from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji, get_zzz_element_emoji
from hoyo_buddy.enums import CharacterType, Game, Platform
from hoyo_buddy.l10n import EnumStr, LevelStr, LocaleStr
from hoyo_buddy.models import HoyolabHSRCharacter
from hoyo_buddy.ui import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Builds, Interaction

    from ..view import Character, ProfileView
    from .build_select import BuildSelect
else:
    ProfileView = None

DATA_TYPES: Final[dict[CharacterType, LocaleStr]] = {
    CharacterType.BUILD: LocaleStr(key="profile.character_select.enka_network.description"),
    CharacterType.LIVE: LocaleStr(key="profile.character_select.live_data.description"),
}
MAX_VALUES: Final[dict[Game, int]] = {Game.GENSHIN: 4, Game.STARRAIL: 4, Game.ZZZ: 3}


def determine_chara_type(character_id: str, *, builds: Builds) -> CharacterType:
    chara_builds = builds.get(character_id, [])
    if chara_builds and not any(build.live for build in chara_builds):
        return CharacterType.BUILD
    return CharacterType.LIVE


class CharacterSelect(PaginatorSelect[ProfileView]):
    def __init__(
        self,
        game: Game,
        characters: Sequence[Character],
        builds: Builds,
        account: HoyoAccount | None,
        character_ids: list[str],
        *,
        row: int,
    ) -> None:
        options: list[SelectOption] = []

        for character in characters:
            character_type = determine_chara_type(str(character.id), builds=builds)
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
                    platform=EnumStr(account.platform if account is not None else Platform.HOYOLAB),
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
            elif isinstance(character, ZZZPartialAgent):
                description = LocaleStr(
                    key="profile.zzz_hoyolab.character_select.description",
                    m=character.rank,
                    platform=EnumStr(account.platform if account is not None else Platform.HOYOLAB),
                )
                emoji = get_zzz_element_emoji(character.element)
            else:
                description = LocaleStr(
                    key="profile.genshin.character_select.hoyolab.description",
                    c=len([c for c in character.constellations if c.unlocked]),
                    r=character.weapon.refinement,
                    d=data_type,
                    platform=EnumStr(account.platform if account is not None else Platform.HOYOLAB),
                )
                emoji = get_gi_element_emoji(character.element)

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
                    default=str(character.id) in character_ids,
                )
            )

        super().__init__(
            options,
            placeholder=LocaleStr(key="profile.character_select.multi.placeholder"),
            custom_id="profile_character_select",
            max_values=min(MAX_VALUES[game], len(options)),
            row=row,
        )

    @staticmethod
    def update_ui(view: ProfileView, *, character_id: str, is_team: bool) -> None:
        # Enable the player info button
        player_btn = view.get_item("profile_player_info")
        player_btn.disabled = False

        # Enable the card settings button
        card_settings_btn = view.get_item("profile_card_settings")
        card_settings_btn.disabled = False

        # Enable the team card settings button
        team_card_settings_btn = view.get_item("profile_team_card_settings")
        team_card_settings_btn.disabled = False

        # Enable the image settings button
        image_settings_btn = view.get_item("profile_image_settings")
        image_settings_btn.disabled = False

        # Enable the redraw card button
        redraw_card_btn = view.get_item("profile_redraw_card")
        redraw_card_btn.disabled = False

        # Set builds
        build_select: BuildSelect = view.get_item("profile_build_select")
        if not is_team and (builds := view._builds.get(character_id)):
            view._build_id = builds[0].id
            build_select.set_options(builds)
            build_select.translate(view.locale)
            build_select.disabled = False
        else:
            build_select.disabled = True

    async def callback(self, i: Interaction) -> Any:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.character_ids = self.values
        is_team = len(self.values) > 1

        character_id = self.view.character_ids[0]
        self.view.character_type = determine_chara_type(character_id, builds=self.view._builds)

        self.update_ui(self.view, character_id=character_id, is_team=is_team)
        self.update_options_defaults()
        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
        return None
