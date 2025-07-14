from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Any, Literal

import discord
from attr import dataclass
from discord import ButtonStyle

from ..emojis import DOUBLE_LEFT, DOUBLE_RIGHT, LEFT, RIGHT
from .components import Button, View

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from ..types import Interaction, User

__all__ = ("Page", "PaginatorView")


@dataclass(kw_only=True)
class Page:
    content: str | None = None
    embed: discord.Embed | None = None
    file: discord.File | None = None


def paginate_content(content: str, *, max_width: int = 2000) -> list[Page]:
    paragraphs = content.split("\n\n")
    all_content: list[str] = []

    for paragraph in paragraphs:
        if paragraph.strip():  # Skip empty paragraphs
            # Wrap each paragraph while preserving its structure
            wrapped_paragraph = textwrap.fill(paragraph.replace("\n", " "), width=max_width)
            all_content.append(wrapped_paragraph)

    # Join paragraphs back with double newlines and split into pages
    full_content = "\n\n".join(all_content)

    # If content is still too long, split into chunks
    if len(full_content) <= max_width:
        return [Page(content=full_content)]

    # Split into chunks while trying to preserve paragraph boundaries
    chunks = []
    current_chunk = ""

    for paragraph in all_content:
        if len(current_chunk) + len(paragraph) + 2 <= max_width:  # +2 for \n\n
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return [Page(content=chunk) for chunk in chunks]


class PaginatorView(View):
    def __init__(
        self,
        pages: dict[int, Page] | list[Page],
        *,
        set_loading_state: bool = False,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self._pages = pages
        self._current_page = 0
        self._max_page = len(pages)
        self._set_loading_state = set_loading_state

        self._add_buttons()

    @property
    def pages(self) -> dict[int, Page] | list[Page]:
        return self._pages

    @pages.setter
    def pages(self, pages: dict[int, Page] | list[Page]) -> None:
        self._pages = pages
        self._max_page = len(pages)

    @property
    def current_page(self) -> int:
        return self._current_page

    @current_page.setter
    def current_page(self, current_page: int) -> None:
        self._current_page = current_page
        self._update_button_states()

    def _add_buttons(self) -> None:
        self.add_item(FirstButton(emoji=DOUBLE_LEFT, custom_id="first_page"))
        self.add_item(
            PreviousButton(emoji=LEFT, style=ButtonStyle.blurple, custom_id="previous_page")
        )
        self.add_item(NextButton(emoji=RIGHT, style=ButtonStyle.blurple, custom_id="next_page"))
        self.add_item(LastButton(emoji=DOUBLE_RIGHT, custom_id="last_page"))

    def _update_button_states(self) -> None:
        """Method to update the disabled state of the buttons."""
        first_button: FirstButton = self.get_item("first_page")
        previous_button: PreviousButton = self.get_item("previous_page")
        next_button: NextButton = self.get_item("next_page")
        last_button: LastButton = self.get_item("last_page")

        first_button.disabled = self._current_page == 0
        previous_button.disabled = self._current_page == 0
        next_button.disabled = self._current_page == self._max_page - 1
        last_button.disabled = self._current_page == self._max_page - 1

    async def _create_file(self) -> discord.File | None:
        """Method to create a file for the current page. Implemented by subclasses."""

    async def _update_page(
        self,
        i: Interaction,
        button: Button[PaginatorView] | None,
        *,
        type_: Literal["next", "prev", "first", "last", "start"],  # noqa: ARG002
        followup: bool = False,
        ephemeral: bool = False,
    ) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=ephemeral)

        try:
            page = self._pages[self._current_page]
        except IndexError:
            return

        self._update_button_states()

        if not followup and button is not None and self._set_loading_state:
            await button.set_loading_state(i)
        file_ = await self._create_file()
        if isinstance(file_, discord.File):
            page.file = file_

        if followup:
            kwargs: dict[str, Any] = {}
            if page.content is not None:
                kwargs["content"] = page.content
            if page.embed is not None:
                kwargs["embed"] = page.embed
            await i.followup.send(
                files=[page.file] if page.file else [], view=self, ephemeral=ephemeral, **kwargs
            )
            self.message = await i.original_response()
        elif button is None or not self._set_loading_state:
            self.message = await i.edit_original_response(
                content=page.content,
                embed=page.embed,
                attachments=[page.file] if page.file else [],
                view=self,
            )
        else:
            await button.unset_loading_state(
                i,
                content=page.content,
                embed=page.embed,
                attachments=[page.file] if page.file else [],
            )
            self.message = await i.original_response()

    async def _next_page(self, i: Interaction, button: Button[PaginatorView]) -> None:
        self._current_page = min(self._current_page + 1, self._max_page)
        await self._update_page(i, button, type_="next")

    async def _previous_page(self, i: Interaction, button: Button[PaginatorView]) -> None:
        self._current_page = max(self._current_page - 1, 0)
        await self._update_page(i, button, type_="prev")

    async def _first_page(self, i: Interaction, button: Button[PaginatorView]) -> None:
        self._current_page = 0
        await self._update_page(i, button, type_="first")

    async def _last_page(self, i: Interaction, button: Button[PaginatorView]) -> None:
        self._current_page = self._max_page - 1
        await self._update_page(i, button, type_="last")

    async def start(
        self, i: Interaction, *, followup: bool = False, ephemeral: bool = False
    ) -> None:
        await self._update_page(i, None, type_="start", followup=followup, ephemeral=ephemeral)


class NextButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._next_page(i, self)


class PreviousButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._previous_page(i, self)


class FirstButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._first_page(i, self)


class LastButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._last_page(i, self)
