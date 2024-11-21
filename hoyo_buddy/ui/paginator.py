from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import discord
from attr import dataclass
from discord import ButtonStyle

from ..emojis import DOUBLE_LEFT, DOUBLE_RIGHT, LEFT, RIGHT
from .components import Button, View

if TYPE_CHECKING:
    from ..types import Interaction


@dataclass(kw_only=True)
class Page:
    content: str | None = None
    embed: discord.Embed | None = None
    file: discord.File | None = None


class PaginatorView(View):
    def __init__(
        self,
        pages: dict[int, Page] | list[Page],
        *,
        author: discord.User | discord.Member | None,
        locale: discord.Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self._pages = pages
        self._current_page = 0
        self._max_page = len(pages)

        self._add_buttons()

    def _add_buttons(self) -> None:
        self.add_item(FirstButton(emoji=DOUBLE_LEFT, custom_id="first_page"))
        self.add_item(PreviousButton(emoji=LEFT, style=ButtonStyle.blurple, custom_id="previous_page"))
        self.add_item(NextButton(emoji=RIGHT, style=ButtonStyle.blurple, custom_id="next_page"))
        self.add_item(LastButton(emoji=DOUBLE_RIGHT, custom_id="last_page"))

    def _upadte_button_state(self) -> None:
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

        file_ = await self._create_file()
        if isinstance(file_, discord.File):
            page.file = file_

        self._upadte_button_state()

        if followup:
            kwargs: dict[str, Any] = {}
            if page.content is not None:
                kwargs["content"] = page.content
            if page.embed is not None:
                kwargs["embed"] = page.embed
            await i.followup.send(files=[page.file] if page.file else [], view=self, ephemeral=ephemeral, **kwargs)
            self.message = await i.original_response()
        else:
            self.message = await i.edit_original_response(
                content=page.content, embed=page.embed, attachments=[page.file] if page.file else [], view=self
            )

    async def _next_page(self, i: Interaction) -> None:
        self._current_page = min(self._current_page + 1, self._max_page)
        await self._update_page(i, type_="next")

    async def _previous_page(self, i: Interaction) -> None:
        self._current_page = max(self._current_page - 1, 0)
        await self._update_page(i, type_="prev")

    async def _first_page(self, i: Interaction) -> None:
        self._current_page = 0
        await self._update_page(i, type_="first")

    async def _last_page(self, i: Interaction) -> None:
        self._current_page = self._max_page - 1
        await self._update_page(i, type_="last")

    async def start(self, i: Interaction, *, followup: bool = False, ephemeral: bool = False) -> None:
        await self._update_page(i, type_="start", followup=followup, ephemeral=ephemeral)


class NextButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._next_page(i)


class PreviousButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._previous_page(i)


class FirstButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._first_page(i)


class LastButton(Button[PaginatorView]):
    async def callback(self, i: Interaction) -> None:
        await self.view._last_page(i)
