from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import enka

from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji, get_zzz_element_emoji
from hoyo_buddy.enums import CharacterType, Game, Platform
from hoyo_buddy.l10n import EnumStr, LevelStr, LocaleStr
from hoyo_buddy.models import HoyolabGICharacter, HoyolabHSRCharacter
from hoyo_buddy.types import HoyolabCharacter
from hoyo_buddy.ui import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Character, Interaction

    from ..view import ProfileView
    from .build_select import BuildSelect
else:
    ProfileView = None

DATA_TYPES: Final[dict[CharacterType, LocaleStr]] = {
    CharacterType.BUILD: LocaleStr(key="profile.character_select.enka_network.description"),
    CharacterType.LIVE: LocaleStr(key="profile.character_select.in_game"),
}
MAX_VALUES: Final[dict[Game, int]] = {Game.GENSHIN: 4, Game.STARRAIL: 4, Game.ZZZ: 3}


class CharacterSelect(PaginatorSelect[ProfileView]):
    def __init__(
        self,
        game: Game,
        characters: Sequence[Character],
        genshin_data: enka.gi.ShowcaseResponse | None,
        starrail_data: enka.hsr.ShowcaseResponse | None,
        zzz_data: enka.zzz.ShowcaseResponse | None,
        account: HoyoAccount | None,
        character_ids: list[str],
        *,
        row: int,
    ) -> None:
        options: list[SelectOption] = []
        showcase_character_ids = self._get_showcase_character_ids(
            genshin_data, starrail_data, zzz_data, game
        )

        for character in characters:
            if isinstance(character, HoyolabCharacter):
                if account is not None:
                    data_type = EnumStr(account.platform)
                else:
                    # Is hoyolab character but no account? Shouldn't happen,
                    # but just in case.
                    data_type = EnumStr(Platform.HOYOLAB)
            else:
                in_showcase = str(character.id) in showcase_character_ids
                character_type = CharacterType.LIVE if in_showcase else CharacterType.BUILD
                data_type = DATA_TYPES[character_type]

            if isinstance(character, enka.hsr.Character | HoyolabHSRCharacter):
                description = LocaleStr(
                    custom_str="{info} | {data_type}",
                    info=LocaleStr(
                        key="profile.character_select.hsr",
                        const=character.eidolons_unlocked,
                        refine=character.light_cone.superimpose
                        if character.light_cone is not None
                        else 0,
                    ),
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element)
            elif isinstance(character, enka.gi.Character | HoyolabGICharacter):
                description = LocaleStr(
                    custom_str="{info} | {data_type}",
                    info=LocaleStr(
                        key="profile.character_select.genshin",
                        const=len([c for c in character.constellations if c.unlocked]),
                        refine=character.weapon.refinement,
                    ),
                    data_type=data_type,
                )
                emoji = get_gi_element_emoji(character.element.name)
            else:
                description = LocaleStr(
                    custom_str="{info} | {data_type}",
                    info=LocaleStr(key="profile.character_select.zzz", const=character.rank),
                    data_type=data_type,
                )
                emoji = get_zzz_element_emoji(character.element)

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
    def _get_showcase_character_ids(
        genshin_data: enka.gi.ShowcaseResponse | None,
        starrail_data: enka.hsr.ShowcaseResponse | None,
        zzz_data: enka.zzz.ShowcaseResponse | None,
        game: Game,
    ) -> set[str]:
        if game is Game.GENSHIN:
            showcase_data = genshin_data
        elif game is Game.STARRAIL:
            showcase_data = starrail_data
        elif game is Game.ZZZ:
            showcase_data = zzz_data
        else:
            showcase_data = None

        if showcase_data is None:
            return set()

        if isinstance(showcase_data, enka.zzz.ShowcaseResponse):
            return {str(character.id) for character in showcase_data.agents}

        return {str(character.id) for character in showcase_data.characters}

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
        showcase_character_ids = CharacterSelect._get_showcase_character_ids(
            view.genshin_data, view.starrail_data, view.zzz_data, view.game
        )
        hoyolab_character_ids = {
            str(character.id)
            for character in view.hoyolab_gi_characters + view.hoyolab_hsr_characters
        }
        build_select: BuildSelect = view.get_item("profile_build_select")
        if not is_team and (builds := view._builds.get(character_id)):
            view._build_id = builds[0].id
            current = (
                None
                if character_id not in {*showcase_character_ids, *hoyolab_character_ids}
                else view.characters[character_id]
            )
            build_select.set_options(builds, current)
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

        self.update_ui(self.view, character_id=character_id, is_team=is_team)
        self.update_options_defaults()
        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
        return None
