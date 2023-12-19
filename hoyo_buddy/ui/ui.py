import logging
from typing import Any, Dict, List, Optional, Self, Sequence, Union

import discord
from discord.utils import MISSING

from ..bot import HoyoBuddy, Translator, emojis
from ..bot import locale_str as _T
from ..bot.error_handler import get_error_embed
from ..db import User
from ..embeds import ErrorEmbed
from ..exceptions import InvalidInput

log = logging.getLogger(__name__)

__all__ = (
    "View",
    "Button",
    "GoBackButton",
    "ToggleButton",
    "SelectOption",
    "Select",
    "TextInput",
    "Modal",
)


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

        user = await User.get(id=i.user.id).prefetch_related("settings")
        locale = user.settings.locale or i.locale
        embed = get_error_embed(error, locale, i.client.translator)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: discord.Interaction[HoyoBuddy]) -> bool:
        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                self.locale,
                self.translator,
                title=_T("Interaction failed", key="interaction_failed_title"),
                description=_T(
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
    def get_embeds(message: Optional[discord.Message]) -> Optional[List[discord.Embed]]:
        if message:
            return message.embeds
        return None

    @staticmethod
    def get_attachments(
        message: Optional[discord.Message],
    ) -> Optional[List[discord.Attachment]]:
        if message:
            return message.attachments
        return None


class Button(discord.ui.Button):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        label: Optional[Union[_T, str]] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[str] = None,
        row: Optional[int] = None,
    ):
        super().__init__(
            style=style,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )

        self.locale_str_label = label
        self.original_label: Optional[str] = None
        self.original_emoji: Optional[str] = None
        self.original_disabled: Optional[bool] = None

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ):
        if self.locale_str_label:
            self.label = translator.translate(self.locale_str_label, locale)

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.view: View
        self.original_label = self.label[:] if self.label else None
        self.original_emoji = str(self.emoji) if self.emoji else None
        self.original_disabled = self.disabled

        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = self.view.translator.translate(
            _T("Loading...", key="loading_text"), self.view.locale
        )
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.view: View
        if self.original_disabled is None:
            raise RuntimeError("unset_loading_state called before set_loading_state")

        self.disabled = self.original_disabled
        self.emoji = self.original_emoji
        self.label = self.original_label
        await self.view.absolute_edit(i, view=self.view)


class GoBackButton(Button):
    def __init__(
        self,
        original_children: List[discord.ui.Item[Any]],
        embeds: Optional[Sequence[discord.Embed]] = None,
        attachments: Optional[Sequence[discord.Attachment]] = None,
        row: int = 4,
    ):
        super().__init__(emoji=emojis.BACK, row=row)
        self.original_children = original_children.copy()
        self.embeds = embeds
        self.attachments = attachments

    async def callback(self, i: discord.Interaction) -> Any:
        self.view.clear_items()
        for item in self.original_children:
            if isinstance(item, (Button, Select)):
                self.view.add_item(item, translate=False)

        kwargs: Dict[str, Any] = {"view": self.view}
        if self.embeds:
            kwargs["embeds"] = self.embeds
        kwargs["attachments"] = self.attachments or []

        await i.response.edit_message(**kwargs)


class ToggleButton(Button):
    def __init__(self, current_toggle: bool, toggle_label: _T, **kwargs):
        self.current_toggle = current_toggle
        self.toggle_label = toggle_label
        super().__init__(
            style=self._get_style(), label=self._get_label(), row=1, **kwargs
        )

    def _get_style(self) -> discord.ButtonStyle:
        return (
            discord.ButtonStyle.success
            if self.current_toggle
            else discord.ButtonStyle.secondary
        )

    def _get_label(self) -> _T:
        return _T(
            "{toggle_label}: {toggle}",
            key="auto_checkin_button_label",
            toggle_label=self.toggle_label,
            toggle=(
                _T("On", key="toggle_on_text")
                if self.current_toggle
                else _T("Off", key="toggle_off_text")
            ),
            translate=False,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: View
        self.current_toggle = not self.current_toggle
        self.style = self._get_style()
        self.label = self.view.translator.translate(self._get_label(), self.view.locale)
        await i.response.edit_message(view=self.view)


class LevelModalButton(Button):
    def __init__(self, *, min: int, max: int, default: Optional[int] = None):
        super().__init__(
            label=_T("Enter level", key="enter_level_button_label"),
            style=discord.ButtonStyle.primary,
        )
        self.min = min
        self.max = max
        self.default = default

    async def callback(self, i: discord.Interaction) -> Any:
        modal = LevelModal(min=self.min, max=self.max, default=self.default)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.level is None:
            return
        self.view.level = modal.level  # type: ignore


class SelectOption(discord.SelectOption):
    def __init__(
        self,
        *,
        label: Union[_T, str],
        value: str,
        description: Optional[Union[_T, str]] = None,
        emoji: Optional[str] = None,
        default: bool = False,
    ) -> None:
        super().__init__(
            label=label if isinstance(label, str) else "#NoTrans",
            value=value,
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
        placeholder: Optional[Union[_T, str]] = None,
        min_values: int = 1,
        max_values: int = 1,
        options: List[SelectOption],
        disabled: bool = False,
        row: Optional[int] = None,
    ) -> None:
        super().__init__(
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            options=options,  # type: ignore
            disabled=disabled,
            row=row,
        )
        self.locale_str_placeholder = placeholder
        self.locale_str_options = options

        self.original_placeholder: Optional[str] = None
        self.original_options: Optional[List[SelectOption]] = None
        self.original_disabled: Optional[bool] = None

    @property
    def options(self) -> List[SelectOption]:
        return self._underlying.options  # type: ignore

    @options.setter
    def options(self, value: List[SelectOption]) -> None:
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
        self.original_options = self.options.copy()
        self.original_placeholder = self.placeholder[:] if self.placeholder else None

        self.options = [
            SelectOption(
                label=self.view.translator.translate(
                    _T("Loading...", key="loading_text"), self.view.locale
                ),
                value="loading",
                default=True,
                emoji=emojis.LOADING,
            )
        ]
        self.disabled = True
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        if not self.original_options or self.original_disabled is None:
            raise RuntimeError("unset_loading_state called before set_loading_state")

        self.options = self.original_options
        self.disabled = self.original_disabled
        self.placeholder = self.original_placeholder
        await self.view.absolute_edit(i, view=self.view)


class TextInput(discord.ui.TextInput):
    def __init__(
        self,
        *,
        label: Union[_T, str],
        style: discord.TextStyle = discord.TextStyle.short,
        custom_id: str = MISSING,
        placeholder: Optional[Union[_T, str]] = None,
        default: Optional[Union[_T, str]] = None,
        required: bool = True,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        row: Optional[int] = None,
    ) -> None:
        super().__init__(
            label=label if isinstance(label, str) else "#NoTrans",
            style=style,
            custom_id=custom_id,
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
        title: Union[_T, str],
        timeout: Optional[float] = None,
        custom_id: str = MISSING,
    ) -> None:
        super().__init__(
            title=title if isinstance(title, str) else "#NoTrans",
            timeout=timeout,
            custom_id=custom_id,
        )
        self.locale_str_title = title

    async def on_error(
        self,
        i: discord.Interaction[HoyoBuddy],
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        user = await User.get(id=i.user.id).prefetch_related("settings")
        locale = user.settings.locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(error)

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


class LevelModal(Modal):
    level_input = TextInput(label=_T("Level", key="level_input_label"))

    def __init__(self, *, min: int, max: int, default: Optional[int] = None):
        super().__init__(title=_T("Enter level", key="enter_level_modal_title"))
        self.min = min
        self.max = max
        self.level_input.default = str(default) if default else None
        self.level_input.placeholder = f"{min} ~ {max}"
        self.level: Optional[int] = None

    async def on_submit(self, i: discord.Interaction) -> None:
        try:
            self.level = int(self.level_input.value)
        except ValueError:
            raise InvalidInput(_T("Level need to be an integer"))

        if self.level < self.min or self.level > self.max:
            raise InvalidInput(
                _T(
                    "Level needs to be between {min} and {max}",
                    min=self.min,
                    max=self.max,
                )
            )

        await i.response.defer()
        self.stop()
