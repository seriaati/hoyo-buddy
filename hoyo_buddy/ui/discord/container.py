from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .action_row import ActionRow
from .section import Section
from .text_display import TextDisplay
from .view import View

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

__all__ = ("Container",)


class Container[V: View](discord.ui.Container):
    def __init__(
        self,
        *children: ActionRow
        | TextDisplay
        | Section
        | discord.ui.MediaGallery
        | discord.ui.File
        | discord.ui.Separator,
        accent_color: discord.Color | int | None = None,
        spoiler: bool = False,
        id: int | None = None,  # noqa: A002
    ) -> None:
        super().__init__(*children, accent_color=accent_color, spoiler=spoiler, id=id)
        self.view: V

    def translate(self, locale: Locale) -> None:
        for child in self.children:
            if isinstance(child, (TextDisplay, ActionRow, Section)):
                child.translate(locale)
