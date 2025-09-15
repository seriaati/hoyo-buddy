from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from genshin.models import ZZZPartialAgent

from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji, get_zzz_element_emoji
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import HoyolabGICharacter, HoyolabHSRCharacter, ZZZEnkaCharacter
from hoyo_buddy.ui import PaginatorSelect, SelectOption
from hoyo_buddy.ui.discord.view import View

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..view import Character


class CharacterSelect[V_co: View](PaginatorSelect):
    def __init__(self, characters: Sequence[Character], character_id: str, *, row: int) -> None:
        self.view: V_co

        self.characters = characters
        self.character_id = character_id
        super().__init__(
            options=self._get_options(),
            placeholder=LocaleStr(key="profile.character_select.placeholder"),
            row=row,
        )

        self.set_page_based_on_value(self.character_id)
        self.options = self.process_options()
        self.update_options_defaults(values=[self.character_id])

    @staticmethod
    def _get_element_emoji(chara: Character) -> str:
        if isinstance(chara, ZZZPartialAgent | ZZZEnkaCharacter):
            return get_zzz_element_emoji(chara.element)
        if isinstance(chara, enka.gi.Character | HoyolabGICharacter):
            return get_gi_element_emoji(chara.element.name)
        if isinstance(chara, enka.hsr.Character | HoyolabHSRCharacter):  # pyright: ignore[reportUnnecessaryIsInstance]
            return get_hsr_element_emoji(str(chara.element))

        msg = f"Unsupported character type: {type(chara)}"
        raise TypeError(msg)

    def _get_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=chara.name,
                value=str(chara.id),
                emoji=self._get_element_emoji(chara),
                default=str(chara.id) == self.character_id,
            )
            for chara in self.characters
        ]
