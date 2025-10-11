from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Self

import discord
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.db import get_locale
from hoyo_buddy.embeds import ErrorEmbed
from hoyo_buddy.l10n import LocaleStr, translator

from .action_row import ActionRow
from .button import Button
from .container import Container
from .section import Section
from .select import Select
from .text_display import TextDisplay

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

__all__ = ("LayoutView", "URLButtonView", "View")


class ViewMixin:
    children: list[discord.ui.Item[Any]]
    author: User
    message: discord.Message | None
    locale: Locale
    clear_items: Callable[[], None]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__module__.replace('hoyo_buddy.ui.', '')}.{self.__class__.__name__}"
        )

    @staticmethod
    async def absolute_send(i: Interaction, **kwargs) -> None:
        with contextlib.suppress(discord.HTTPException):
            if not i.response.is_done():
                await i.response.send_message(**kwargs)
            else:
                await i.followup.send(**kwargs)

    @staticmethod
    async def absolute_edit(i: Interaction, **kwargs) -> None:
        with contextlib.suppress(discord.HTTPException):
            if not i.response.is_done():
                await i.response.edit_message(**kwargs)
            else:
                await i.edit_original_response(**kwargs)

    @staticmethod
    def get_embeds(message: discord.Message | None) -> list[discord.Embed] | None:
        if message:
            return message.embeds
        return None

    async def on_timeout(self) -> None:
        all_url_buttons = all(
            item.url for item in self.children if isinstance(item, (discord.ui.Button))
        )
        if self.message is not None and not all_url_buttons:
            self.clear_items()
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)  # pyright: ignore[reportArgumentType]

        if self.message is None and not all_url_buttons:
            logger.warning(f"View {self!r} timed out without a set message")

    async def on_error(self, i: Interaction, error: Exception, item: discord.ui.Item[Any]) -> None:
        locale = await get_locale(i)
        embed, recognized = get_error_embed(error, locale)
        if not recognized:
            i.client.capture_exception(error)

        with contextlib.suppress(Exception):
            await item.unset_loading_state(i)  # pyright: ignore[reportAttributeAccessIssue]
            await self.absolute_edit(i)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: Interaction) -> bool:
        if self.author is None:
            return True

        locale = await get_locale(i)

        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                locale,
                title=LocaleStr(key="interaction_failed_title"),
                description=LocaleStr(key="interaction_failed_description"),
            )
            await i.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def get_item(self, custom_id: str) -> Any:
        for item in self.children:
            if isinstance(item, Button | Select) and item.custom_id == custom_id:
                return item

        msg = f"No item found with custom_id {custom_id!r}"
        raise ValueError(msg)


class View(discord.ui.View, ViewMixin):
    def __init__(self, *, author: User, locale: Locale) -> None:
        super().__init__(timeout=600)
        self.author = author
        self.locale = locale
        self.message: discord.Message | None = None
        self.item_states: dict[str, bool] = {}

    def add_items(self, items: Iterable[Button | Select]) -> Self:
        for item in items:
            self.add_item(item)
        return self

    def disable_items(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                if child.custom_id is not None:
                    self.item_states[child.custom_id] = child.disabled

                if isinstance(child, discord.ui.Button) and child.url:
                    continue

                child.disabled = True

    def enable_items(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                if isinstance(child, discord.ui.Button) and child.url:
                    continue

                if child.custom_id is not None:
                    child.disabled = self.item_states.get(child.custom_id, False)
                else:
                    # Cannot determine the original state of the item
                    child.disabled = False

    def add_item(self, item: Button | Select, *, translate: bool = True) -> Self:
        if translate:
            item.translate(self.locale)
        return super().add_item(item)

    def translate_items(self) -> None:
        for item in self.children:
            if isinstance(item, Button | Select):
                item.translate(self.locale)


class URLButtonView(discord.ui.View):
    def __init__(
        self,
        locale: Locale,
        *,
        url: str,
        label: str | LocaleStr | None = None,
        emoji: str | None = None,
    ) -> None:
        super().__init__()
        self.add_item(
            discord.ui.Button(
                label=translator.translate(label, locale) if label else None, url=url, emoji=emoji
            )
        )


class LayoutView(discord.ui.LayoutView, ViewMixin):
    def __init__(self, *, author: User, locale: Locale) -> None:
        super().__init__(timeout=600)
        self.author = author
        self.locale = locale
        self.message: discord.Message | None = None
        self.item_states: dict[str, bool] = {}

        self.translate(locale)

    def translate(self, locale: Locale) -> None:
        for child in self.children:
            if isinstance(child, (ActionRow, Container, Section, TextDisplay)):
                child.translate(locale)
