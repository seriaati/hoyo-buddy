import logging
from typing import Any, List, Optional, Self, Sequence, Union

import discord
from discord.app_commands import locale_str
from discord.utils import MISSING

from ..bot import HoyoBuddy, emojis
from ..bot.translator import Translator
from ..bot.embeds import ErrorEmbed

log = logging.getLogger(__name__)


class View(discord.ui.View):
    def __init__(
        self,
        *,
        author: Union[discord.Member, discord.User],
        locale: discord.Locale,
        translator: Translator,
        timeout: Optional[float] = 180,
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.locale = locale
        self.translator = translator
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        if self.message:
            self.disable_items()
            await self.message.edit(view=self)

    async def on_error(
        self,
        i: discord.Interaction[HoyoBuddy],
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        i.client.capture_exception(error)
        embed = await get_error_embed(i, error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: discord.Interaction[HoyoBuddy]) -> bool:
        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                self.locale,
                self.translator,
                title=locale_str("Interaction failed", key="interaction_failed_title"),
                description=locale_str(
                    "This view is not initiated by you, therefore you cannot use it.",
                    key="interaction_failed_description",
                ),
            )
            await i.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def disable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True

    def enable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = False

    def add_item(
        self, item: Union["Button", "Select"], *, translate: bool = True
    ) -> Self:
        if translate:
            item.translate(self.locale, self.translator)
        return super().add_item(item)

    def get_item(self, custom_id: str) -> Optional[Union["Button", "Select"]]:
        for item in self.children:
            if isinstance(item, (Button, Select)) and item.custom_id == custom_id:
                return item
        return None

    @staticmethod
    async def absolute_send(i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)

    @staticmethod
    async def absolute_edit(i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await i.edit_original_response(**kwargs)

    @staticmethod
    def get_embed(i: discord.Interaction) -> Optional[discord.Embed]:
        if i.message and i.message.embeds:
            return i.message.embeds[0]
        return None


class Button(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        label: Optional[locale_str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[str] = None,
        row: Optional[int] = None,
    ):
        self.locale_str_label = label
        self.original_label: Optional[str] = None
        self.original_emoji = emoji

        super().__init__(
            style=style,
            label=label.message if label else None,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ):
        if self.locale_str_label:
            self.label = translator.translate(self.locale_str_label, locale)
            self.original_label = self.label[:]

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.view: View
        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = self.view.translator.translate(
            locale_str("Loading...", key="loading_text"), self.view.locale
        )
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.view: View
        self.disabled = False
        self.emoji = self.original_emoji
        self.label = self.original_label
        await self.view.absolute_edit(i, view=self.view)


class GoBackButton(Button):
    def __init__(
        self,
        original_children: List[discord.ui.Item[Any]],
        embed: Optional[discord.Embed] = None,
        row: int = 4,
    ):
        super().__init__(emoji=emojis.BACK, row=row)
        self.original_children = original_children.copy()
        self.embed = embed

    async def callback(self, i: discord.Interaction) -> Any:
        self.view.clear_items()
        for item in self.original_children:
            if isinstance(item, (Button, Select)):
                self.view.add_item(item, translate=False)

        if self.embed:
            await i.response.edit_message(embed=self.embed, view=self.view)
        else:
            await i.response.edit_message(view=self.view)


class SelectOption(discord.SelectOption):
    def __init__(
        self,
        *,
        label: locale_str,
        value: str,
        description: Optional[locale_str] = None,
        emoji: Optional[str] = None,
        default: bool = False,
    ) -> None:
        super().__init__(
            label=label.message,
            value=value,
            description=description.message if description else None,
            emoji=emoji,
            default=default,
        )
        self.locale_str_label = label
        self.locale_str_description = description


class Select(discord.ui.Select):
    def __init__(
        self,
        *,
        custom_id: str = MISSING,
        placeholder: Optional[locale_str] = None,
        min_values: int = 1,
        max_values: int = 1,
        options: List[SelectOption] = MISSING,
        disabled: bool = False,
        row: Optional[int] = None,
    ) -> None:
        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder.message if placeholder else None,
            min_values=min_values,
            max_values=max_values,
            options=options,  # type: ignore
            disabled=disabled,
            row=row,
        )
        self.original_placeholder = placeholder
        self.original_options = self.options.copy()
        self.locale_str_placeholder = placeholder
        self.locale_str_options = options

    @property
    def options(self) -> List[discord.SelectOption]:
        return self._underlying.options

    @options.setter
    def options(self, value: Sequence[discord.SelectOption]) -> None:
        if not isinstance(value, list):
            raise TypeError("options must be a list of SelectOption")
        if not all(isinstance(obj, SelectOption) for obj in value):
            raise TypeError("all list items must subclass SelectOption")

        self._underlying.options = value  # type: ignore

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ) -> None:
        if self.locale_str_placeholder:
            self.placeholder = translator.translate(self.locale_str_placeholder, locale)
        for option in self.locale_str_options:
            option.label = translator.translate(option.locale_str_label, locale)
            if option.locale_str_description:
                option.description = translator.translate(
                    option.locale_str_description, locale
                )

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.view: View
        self.options = [
            SelectOption(
                label=locale_str("Loading...", key="loading_text"),
                value="loading",
                default=True,
                emoji=emojis.LOADING,
            )
        ]
        self.disabled = True
        self.translate(self.view.locale, self.view.translator)
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.options = self.original_options.copy()
        self.disabled = False
        self.placeholder = (
            self.original_placeholder.message if self.original_placeholder else None
        )
        self.translate(self.view.locale, self.view.translator)
        await self.view.absolute_edit(i, view=self.view)


class TextInput(discord.ui.TextInput):
    def __init__(
        self,
        *,
        label: locale_str,
        style: discord.TextStyle = discord.TextStyle.short,
        custom_id: str = MISSING,
        placeholder: Optional[locale_str] = None,
        default: Optional[locale_str] = None,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        row: Optional[int] = None,
    ) -> None:
        super().__init__(
            label=label.message,
            style=style,
            custom_id=custom_id,
            placeholder=placeholder.message if placeholder else None,
            default=default.message if default else None,
            required=required,
            min_length=min_length,
            max_length=max_length,
            row=row,
        )
        self.locale_str_label = label
        self.locale_str_placeholder = placeholder
        self.locale_str_default = default


class Modal(discord.ui.Modal):
    def __init__(
        self,
        *,
        title: locale_str,
        timeout: Optional[float] = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(title=title.message, timeout=timeout, custom_id=custom_id)
        self.locale_str_title = title

    async def on_error(
        self,
        i: discord.Interaction[HoyoBuddy],
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        i.client.capture_exception(error)
        embed = await get_error_embed(i, error)
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, i: discord.Interaction) -> None:
        await i.response.defer()
        self.stop()

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ) -> None:
        self.title = translator.translate(
            self.locale_str_title,
            locale,
        )
        for item in self.children:
            if isinstance(item, TextInput):
                item.label = translator.translate(item.locale_str_label, locale)
                if item.locale_str_placeholder:
                    item.placeholder = translator.translate(
                        item.locale_str_placeholder, locale
                    )
                if item.locale_str_default:
                    item.default = translator.translate(item.locale_str_default, locale)
