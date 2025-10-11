from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .button import Button
from .select import Select

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .view import View

__all__ = ("ActionRow",)


class ActionRow[V: View](discord.ui.ActionRow):
    def __init__(self, *children: Button[V] | Select[V], id: int | None = None) -> None:  # noqa: A002
        super().__init__(*children, id=id)

        self.view: V

    def translate(self, locale: Locale) -> None:
        for child in self.children:
            if isinstance(child, (Button, Select)):
                child.translate(locale)
