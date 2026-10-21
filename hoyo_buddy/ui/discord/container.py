from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy.emojis import GAME_ICON_EMOJIS
from hoyo_buddy.utils.misc import is_valid_hex_color

from .action_row import ActionRow
from .section import Section
from .text_display import TextDisplay

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .view import LayoutView

__all__ = ("Container", "DefaultContainer", "EmbedContainer")

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
        accent_color: discord.Color | int | str | None = None,
        spoiler: bool = False,
        id: int | None = None,  # ruff:ignore[builtin-argument-shadowing]
    ) -> None:
        if isinstance(accent_color, str):
            if not is_valid_hex_color(accent_color):
                msg = f"Invalid hex color string: {accent_color}"
                raise ValueError(msg)
            accent_color = discord.Color(int(str(accent_color).lstrip("#"), 16))

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

    def enable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (ActionRow, Section)):
                child.enable_items()


class DefaultContainer[V: LayoutView](Container):
    def __init__(
        self,
        *children: ContainerItem,
        spoiler: bool = False,
        id: int | None = None,  # ruff:ignore[builtin-argument-shadowing]
    ) -> None:
        super().__init__(*children, accent_color=discord.Color(6649080), spoiler=spoiler, id=id)
        self.view: V


class EmbedContainer[V: LayoutView](Container):
    """Renders an embed's content as Components V2 items, followed by the given children."""

    def __init__(self, embed: discord.Embed, *children: ContainerItem) -> None:
        items = self._embed_to_items(embed)
        if children:
            items.extend((discord.ui.Separator(spacing=discord.SeparatorSpacing.large), *children))

        super().__init__(*items, accent_color=embed.color)
        self.view: V

    @staticmethod
    def _embed_to_items(embed: discord.Embed) -> list[ContainerItem]:
        items: list[ContainerItem] = []

        if embed.author.name:
            author = embed.author.name
            if embed.author.url:
                author = f"[{author}]({embed.author.url})"
            if emoji := GAME_ICON_EMOJIS.get(embed.author.icon_url or ""):
                author = f"{emoji} {author}"
            items.append(TextDisplay(author))

        lines: list[str] = []
        if embed.title:
            lines.append(f"### [{embed.title}]({embed.url})" if embed.url else f"### {embed.title}")
        if embed.description:
            lines.append(embed.description)
        for field in embed.fields:
            value = str(field.value)
            if field.inline and "\n" not in value and not value.startswith(("* ", "- ")):
                lines.append(f"**{field.name}**: {field.value}")
            else:
                lines.append(f"**{field.name}**\n{field.value}")

        if lines:
            body = TextDisplay("\n".join(lines))
            if embed.thumbnail.url:
                items.append(Section(body, accessory=discord.ui.Thumbnail(embed.thumbnail.url)))
            else:
                items.append(body)

        if embed.image.url:
            items.append(discord.ui.MediaGallery(discord.MediaGalleryItem(embed.image.url)))

        if embed.footer.text:
            items.append(
                TextDisplay("\n".join(f"-# {line}" for line in embed.footer.text.splitlines()))
            )

        return items
