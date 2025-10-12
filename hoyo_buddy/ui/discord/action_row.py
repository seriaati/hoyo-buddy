from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .button import Button

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .select import Select
    from .view import View

__all__ = ("ActionRow",)


class ActionRow[V: View](discord.ui.ActionRow):
    def __init__(self, *children: Button | Select, id: int | None = None) -> None:  # noqa: A002
        super().__init__(*children, id=id)

        self.view: V
        self.children: list[Button | Select]

    def translate(self, locale: Locale) -> None:
        for child in self.children:
            child.translate(locale)

    def disable_items(self) -> None:
        for item in self.children:
            if item.custom_id is not None:
                self.view.item_states[item.custom_id] = item.disabled

            if isinstance(item, Button) and item.url:
                continue

            item.disabled = True
