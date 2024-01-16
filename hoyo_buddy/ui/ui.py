from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

import discord
from discord.utils import MISSING

from ..bot import INTERACTION, LocaleStr, Translator, emojis
from ..bot.error_handler import get_error_embed
from ..db.models import Settings
from ..embeds import ErrorEmbed
from ..exceptions import InvalidInputError
from ..utils import split_list

if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = (
    "View",
    "Button",
    "GoBackButton",
    "ToggleButton",
    "SelectOption",
    "Select",
    "TextInput",
    "Modal",
    "LevelModal",
    "LevelModalButton",
    "PaginatorSelect",
    "URLButtonView",
)

V_co = TypeVar("V_co", bound="View", covariant=True)


class View(discord.ui.View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member,
        locale: discord.Locale,
        translator: Translator,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author = author
        self.locale = locale
        self.translator = translator
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        if self.message:
            self.disable_items()
            await self.message.edit(view=self)

    async def on_error(
        self,
        i: INTERACTION,
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        i.client.capture_exception(error)

        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: INTERACTION) -> bool:
        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Interaction failed", key="interaction_failed_title"),
                description=LocaleStr(
                    "This view is not initiated by you, therefore you cannot use it.",
                    key="interaction_failed_description",
                ),
            )
            await i.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    def disable_items(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                child.disabled = True

    def enable_items(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button | discord.ui.Select):
                child.disabled = False

    def add_item(self, item: "Button | Select", *, translate: bool = True) -> Self:
        if translate:
            item.translate(self.locale, self.translator)
        return super().add_item(item)

    def get_item(self, custom_id: str) -> "Button | Select | None":
        for item in self.children:
            if isinstance(item, Button | Select) and item.custom_id == custom_id:
                return item
        return None

    @staticmethod
    async def absolute_send(i: INTERACTION, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)

    @staticmethod
    async def absolute_edit(i: INTERACTION, **kwargs) -> None:
        try:
            await i.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await i.edit_original_response(**kwargs)

    @staticmethod
    def get_embeds(message: discord.Message | None) -> list[discord.Embed] | None:
        if message:
            return message.embeds
        return None

    @staticmethod
    def get_attachments(
        message: discord.Message | None,
    ) -> list[discord.Attachment] | None:
        if message:
            return message.attachments
        return None


class URLButtonView(discord.ui.View):
    def __init__(
        self,
        translator: Translator,
        locale: discord.Locale,
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


class Button(discord.ui.Button, Generic[V_co]):
    def __init__(
        self,
        *,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        label: LocaleStr | str | None = None,
        disabled: bool = False,
        custom_id: str | None = None,
        url: str | None = None,
        emoji: str | None = None,
        row: int | None = None,
    ) -> None:
        super().__init__(
            style=style,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )

        self.locale_str_label = label
        self.original_label: str | None = None
        self.original_emoji: str | None = None
        self.original_disabled: bool | None = None

        self.view: V_co

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ) -> None:
        if self.locale_str_label:
            self.label = translator.translate(self.locale_str_label, locale)

    async def set_loading_state(self, i: INTERACTION) -> None:
        self.original_label = self.label[:] if self.label else None
        self.original_emoji = str(self.emoji) if self.emoji else None
        self.original_disabled = self.disabled

        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = self.view.translator.translate(
            LocaleStr("Loading...", key="loading_text"), self.view.locale
        )
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: INTERACTION) -> None:
        if self.original_disabled is None:
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.disabled = self.original_disabled
        self.emoji = self.original_emoji
        self.label = self.original_label
        await self.view.absolute_edit(i, view=self.view)


class GoBackButton(Button, Generic[V_co]):
    def __init__(
        self,
        original_children: list[discord.ui.Item[Any]],
        embeds: "Sequence[discord.Embed] | None" = None,
        attachments: "Sequence[discord.Attachment] | None" = None,
        row: int = 4,
    ) -> None:
        super().__init__(emoji=emojis.BACK, row=row)
        self.original_children = original_children.copy()
        self.embeds = embeds
        self.attachments = attachments

        self.view: V_co

    async def callback(self, i: INTERACTION) -> Any:
        self.view.clear_items()
        for item in self.original_children:
            if isinstance(item, Button | Select):
                self.view.add_item(item, translate=False)

        kwargs: dict[str, Any] = {"view": self.view}
        if self.embeds:
            kwargs["embeds"] = self.embeds
        kwargs["attachments"] = self.attachments or []

        await i.response.edit_message(**kwargs)


class ToggleButton(Button, Generic[V_co]):
    def __init__(self, current_toggle: bool, toggle_label: LocaleStr, **kwargs) -> None:
        self.current_toggle = current_toggle
        self.toggle_label = toggle_label
        super().__init__(style=self._get_style(), label=self._get_label(), row=1, **kwargs)

        self.view: V_co

    def _get_style(self) -> discord.ButtonStyle:
        return discord.ButtonStyle.success if self.current_toggle else discord.ButtonStyle.secondary

    def _get_label(self) -> LocaleStr:
        return LocaleStr(
            "{toggle_label}: {toggle}",
            key="auto_checkin_button_label",
            toggle_label=self.toggle_label,
            toggle=(
                LocaleStr("On", key="toggle_on_text")
                if self.current_toggle
                else LocaleStr("Off", key="toggle_off_text")
            ),
            translate=False,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.current_toggle = not self.current_toggle
        self.style = self._get_style()
        self.label = self.view.translator.translate(self._get_label(), self.view.locale)
        await i.response.edit_message(view=self.view)


class LevelModalButton(Button, Generic[V_co]):
    def __init__(
        self,
        *,
        min_level: int,
        max_level: int,
        default_level: int | None = None,
        label: LocaleStr | str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            label=label or LocaleStr("Enter level", key="enter_level_button_label"),
            style=discord.ButtonStyle.primary,
            **kwargs,
        )
        self.level: int
        self.min_level = min_level
        self.max_level = max_level
        self.default = default_level

        self.view: V_co

    async def callback(self, i: INTERACTION) -> Any:
        modal = LevelModal(
            min_level=self.min_level, max_level=self.max_level, default_level=self.default
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.level is None:
            return
        self.level = modal.level


class SelectOption(discord.SelectOption):
    def __init__(
        self,
        *,
        label: LocaleStr | str,
        value: str,
        description: LocaleStr | str | None = None,
        emoji: str | None = None,
        default: bool = False,
    ) -> None:
        super().__init__(
            label=label if isinstance(label, str) else label.message,
            value=value,
            emoji=emoji,
            default=default,
        )
        self.locale_str_label = label
        self.locale_str_description = description


class Select(discord.ui.Select, Generic[V_co]):
    def __init__(
        self,
        *,
        custom_id: str = MISSING,
        placeholder: LocaleStr | str | None = None,
        min_values: int = 1,
        max_values: int = 1,
        options: list[SelectOption],
        disabled: bool = False,
        row: int | None = None,
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

        self.original_placeholder: str | None = None
        self.original_options: list[SelectOption] | None = None
        self.original_disabled: bool | None = None

        self.view: V_co

    @property
    def options(self) -> list[SelectOption]:
        return self._underlying.options  # type: ignore

    @options.setter
    def options(self, value: list[SelectOption]) -> None:
        self._underlying.options = value  # type: ignore

    def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
    ) -> None:
        if self.locale_str_placeholder:
            self.placeholder = translator.translate(self.locale_str_placeholder, locale)
        for option in self.options:
            option.label = translator.translate(option.locale_str_label, locale)
            if option.locale_str_description:
                option.description = translator.translate(option.locale_str_description, locale)

    async def set_loading_state(self, i: INTERACTION) -> None:
        self.original_options = self.options.copy()
        self.original_placeholder = self.placeholder[:] if self.placeholder else None

        self.options = [
            SelectOption(
                label=self.view.translator.translate(
                    LocaleStr("Loading...", key="loading_text"), self.view.locale
                ),
                value="loading",
                default=True,
                emoji=emojis.LOADING,
            )
        ]
        self.disabled = True
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: INTERACTION) -> None:
        if not self.original_options or self.original_disabled is None:
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.options = self.original_options
        self.disabled = self.original_disabled
        self.placeholder = self.original_placeholder
        await self.view.absolute_edit(i, view=self.view)

    def set_current_options(self) -> None:
        for option in self.options:
            if option.value in self.values:
                option.default = True
            else:
                option.default = False


NEXT_PAGE = SelectOption(
    label=LocaleStr("Next page", key="next_page_option_label"),
    value="next_page",
    emoji=emojis.FORWARD,
)
PREV_PAGE = SelectOption(
    label=LocaleStr("Previous page", key="prev_page_option_label"),
    value="prev_page",
    emoji=emojis.BACK,
)


class PaginatorSelect(Select, Generic[V_co]):
    def __init__(
        self,
        options: list[SelectOption],
        **kwargs,
    ) -> None:
        self.split_options = split_list(options, 23)
        self.page_index = 0
        super().__init__(options=self._process_options(), **kwargs)

        self.view: V_co

    def _process_options(self) -> list[SelectOption]:
        if self.page_index == 0:
            if len(self.split_options) == 1:
                return self.split_options[0]
            return self.split_options[0] + [NEXT_PAGE]
        if self.page_index == len(self.split_options) - 1:
            return [PREV_PAGE] + self.split_options[-1]
        return [PREV_PAGE] + self.split_options[self.page_index] + [NEXT_PAGE]

    async def callback(self) -> Any:
        if self.values[0] == "next_page":
            self.page_index += 1
            self.options = self._process_options()
        elif self.values[0] == "prev_page":
            self.page_index -= 1
            self.options = self._process_options()

        self.translate(self.view.locale, self.view.translator)


class TextInput(discord.ui.TextInput):
    def __init__(
        self,
        *,
        label: LocaleStr | str,
        style: discord.TextStyle = discord.TextStyle.short,
        custom_id: str = MISSING,
        placeholder: LocaleStr | str | None = None,
        default: LocaleStr | str | None = None,
        required: bool = True,
        min_length: int | None = None,
        max_length: int | None = None,
        row: int | None = None,
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
        title: LocaleStr | str,
        timeout: float | None = None,
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
        i: INTERACTION,
        error: Exception,
    ) -> None:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(error)

        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, i: INTERACTION) -> None:
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
                    item.placeholder = translator.translate(item.locale_str_placeholder, locale)
                if item.locale_str_default:
                    item.default = translator.translate(item.locale_str_default, locale)


class LevelModal(Modal):
    level_input = TextInput(label=LocaleStr("Level", key="level_input_label"))

    def __init__(self, *, min_level: int, max_level: int, default_level: int | None = None) -> None:
        super().__init__(title=LocaleStr("Enter level", key="enter_level_modal_title"))
        self.min_level = min_level
        self.max_level = max_level
        self.level_input.default = str(default_level) if default_level else None
        self.level_input.placeholder = f"{min_level} ~ {max_level}"
        self.level: int | None = None

    async def on_submit(self, i: INTERACTION) -> None:
        try:
            self.level = int(self.level_input.value)
        except ValueError:
            raise InvalidInputError(LocaleStr("Level need to be an integer")) from None

        if self.level < self.min_level or self.level > self.max_level:
            raise InvalidInputError(
                LocaleStr(
                    "Level needs to be between {min_level} and {max_level}",
                    key="level_out_of_range",
                    min_level=self.min_level,
                    max_level=self.max_level,
                )
            )

        await i.response.defer()
        self.stop()
