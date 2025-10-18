from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .button import Button
from .text_display import TextDisplay

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .view import View

__all__ = ("Section",)


class Section[V: View](discord.ui.Section):
    def __init__(
        self,
        *children: TextDisplay,
        accessory: Button | discord.ui.Thumbnail,
        id: int | None = None,  # noqa: A002
    ) -> None:
        super().__init__(*children, accessory=accessory, id=id)
        self.view: V

    def translate(self, locale: Locale) -> None:
        for child in self.children:
            if isinstance(child, TextDisplay):
                child.translate(locale)
        if isinstance(self.accessory, Button):
            self.accessory.translate(locale)

    def disable_items(self) -> None:
        if isinstance(self.accessory, Button):
            if self.accessory.custom_id is not None:
                self.view.item_states[self.accessory.custom_id] = self.accessory.disabled

            if self.accessory.url:
                return

            self.accessory.disabled = True
