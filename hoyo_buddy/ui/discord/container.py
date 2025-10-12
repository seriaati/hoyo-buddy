from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .action_row import ActionRow
from .section import Section
from .text_display import TextDisplay

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .view import LayoutView

__all__ = ("Container", "DefaultContainer")

type ContainerItem = (
    ActionRow
    | TextDisplay
    | Section
    | discord.ui.MediaGallery
    | discord.ui.File
    | discord.ui.Separator
)


class Container[V: LayoutView](discord.ui.Container):
    def __init__(
        self,
        *children: ContainerItem,
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

    def disable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (ActionRow, Section)):
                child.disable_items()


class DefaultContainer[V: LayoutView](Container):
    def __init__(
        self,
        *children: ContainerItem,
        spoiler: bool = False,
        id: int | None = None,  # noqa: A002
    ) -> None:
        super().__init__(*children, accent_color=discord.Color(6649080), spoiler=spoiler, id=id)
        self.view: V
