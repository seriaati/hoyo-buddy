import contextlib
import logging
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

import discord
from discord.utils import MISSING
from seria.utils import split_list_to_chunks

from .. import emojis
from ..bot.error_handler import get_error_embed
from ..bot.translator import LocaleStr, Translator
from ..db.models import Settings
from ..embeds import ErrorEmbed
from ..exceptions import InvalidInputError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..bot.bot import INTERACTION


__all__ = (
    "View",
    "Button",
    "GoBackButton",
    "ToggleButton",
    "SelectOption",
    "Select",
    "TextInput",
    "Modal",
    "PaginatorSelect",
    "URLButtonView",
)

V_co = TypeVar("V_co", bound="View", covariant=True)
LOGGER_ = logging.getLogger(__name__)


class View(discord.ui.View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member | None,
        locale: discord.Locale,
        translator: Translator,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(timeout=timeout)
        self.author = author
        self.locale = locale
        self.translator = translator
        self.message: discord.Message | None = None

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__module__.replace('hoyo_buddy.ui.', '')}.{self.__class__.__name__}"
        )

    async def on_timeout(self) -> None:
        if self.message:
            self.disable_items()
            with contextlib.suppress(discord.NotFound, discord.HTTPException):
                await self.message.edit(view=self)
        else:
            LOGGER_.error("View %r timed out without a set message", self)

    async def on_error(
        self,
        i: "INTERACTION",
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: "INTERACTION") -> bool:
        if self.author is None:
            return True

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

    def get_item(self, custom_id: str) -> Any:
        for item in self.children:
            if isinstance(item, Button | Select) and item.custom_id == custom_id:
                return item
        msg = f"No item found with custom_id {custom_id}"
        raise ValueError(msg)

    def translate_items(self) -> None:
        for item in self.children:
            if isinstance(item, Button | Select):
                item.translate(self.locale, self.translator)

    @staticmethod
    async def absolute_send(i: "INTERACTION", **kwargs: Any) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)
        except discord.NotFound:
            pass

    @staticmethod
    async def absolute_edit(i: "INTERACTION", **kwargs: Any) -> None:
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

    async def set_loading_state(self, i: "INTERACTION") -> None:
        self.original_label = self.label[:] if self.label else None
        self.original_emoji = str(self.emoji) if self.emoji else None
        self.original_disabled = self.disabled

        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = self.view.translator.translate(
            LocaleStr("Loading...", key="loading_text"), self.view.locale
        )
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: "INTERACTION", **kwargs: Any) -> None:
        if self.original_disabled is None:
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.disabled = self.original_disabled
        self.emoji = self.original_emoji
        self.label = self.original_label
        await self.view.absolute_edit(i, view=self.view, **kwargs)


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

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.clear_items()
        for item in self.original_children:
            if isinstance(item, Button | Select):
                self.view.add_item(item, translate=False)

        kwargs: dict[str, Any] = {"view": self.view}
        if self.embeds is not None:
            kwargs["embeds"] = self.embeds
        if self.attachments is not None:
            kwargs["attachments"] = [await attachment.to_file() for attachment in self.attachments]

        await i.response.edit_message(**kwargs)


class ToggleButton(Button, Generic[V_co]):
    def __init__(self, current_toggle: bool, toggle_label: LocaleStr, **kwargs: Any) -> None:
        self.current_toggle = current_toggle
        self.toggle_label = toggle_label
        kwargs["row"] = kwargs.get("row", 1)
        super().__init__(style=self._get_style(), label=self._get_label(), **kwargs)

        self.view: V_co

    def _get_style(self) -> discord.ButtonStyle:
        return discord.ButtonStyle.success if self.current_toggle else discord.ButtonStyle.secondary

    def _get_label(self) -> LocaleStr:
        return LocaleStr(
            "{toggle_label}: {toggle}",
            key="toggle_button_label",
            toggle_label=self.toggle_label,
            toggle=(
                LocaleStr("On", key="toggle_on_text")
                if self.current_toggle
                else LocaleStr("Off", key="toggle_off_text")
            ),
            translate=False,
        )

    async def callback(self, i: "INTERACTION", *, edit: bool = True, **kwargs: Any) -> Any:
        self.current_toggle = not self.current_toggle
        self.style = self._get_style()
        self.label = self.view.translator.translate(self._get_label(), self.view.locale)
        if edit:
            await i.response.edit_message(view=self.view, **kwargs)


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
        self.original_max_values: int | None = None
        self.original_min_values: int | None = None

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
            # NOTE: This is a workaround for a bug(?) in discord.py where options somehow get converted to discord.components.SelectOption internally
            if not isinstance(option, SelectOption):
                continue
            option.label = translator.translate(option.locale_str_label, locale)
            if option.locale_str_description:
                option.description = translator.translate(option.locale_str_description, locale)

    async def set_loading_state(self, i: "INTERACTION") -> None:
        self.original_options = self.options.copy()
        self.original_disabled = self.disabled
        self.original_placeholder = self.placeholder[:] if self.placeholder else None
        self.original_max_values = self.max_values
        self.original_min_values = self.min_values

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
        self.max_values = 1
        self.min_values = 1
        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: "INTERACTION", **kwargs: Any) -> None:
        if (
            not self.original_options
            or self.original_disabled is None
            or self.original_max_values is None
            or self.original_min_values is None
        ):
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.options = self.original_options
        self.disabled = self.original_disabled
        self.placeholder = self.original_placeholder
        self.max_values = self.original_max_values
        self.min_values = self.original_min_values

        self.update_options_defaults()

        await self.view.absolute_edit(i, view=self.view, **kwargs)

    def update_options_defaults(self, *, values: list[str] | None = None) -> None:
        values = values or self.values
        for option in self.options:
            option.default = option.value in values


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
        **kwargs: Any,
    ) -> None:
        self.options_before_split = options
        self.page_index = 0
        super().__init__(options=self.process_options(), **kwargs)

        self.view: V_co

    def process_options(self) -> list[SelectOption]:
        split_options = split_list_to_chunks(self.options_before_split, 23)

        if self.page_index == 0:
            if len(split_options) == 1:
                return split_options[0]
            return split_options[0] + [NEXT_PAGE]
        if self.page_index == len(split_options) - 1:
            return [PREV_PAGE] + split_options[-1]
        return [PREV_PAGE] + split_options[self.page_index] + [NEXT_PAGE]

    def set_page_based_on_value(self, value: str) -> None:
        split_options = split_list_to_chunks(self.options_before_split, 23)

        for i, options in enumerate(split_options):
            if value in [option.value for option in options]:
                self.page_index = i
                break

    async def callback(self) -> bool:
        changed = False
        if self.values[0] == "next_page":
            changed = True
            self.page_index += 1
            self.options = self.process_options()
        elif self.values[0] == "prev_page":
            changed = True
            self.page_index -= 1
            self.options = self.process_options()

        if changed:
            for option in self.options:
                option.default = False

        self.translate(self.view.locale, self.view.translator)
        return changed


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
        is_digit: bool = False,
        max_value: int | None = None,
        min_value: int | None = None,
        is_bool: bool = False,
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

        self.is_digit = is_digit
        self.max_value = max_value
        self.min_value = min_value
        self.is_bool = is_bool


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
            custom_id=self.__class__.__name__ if custom_id is MISSING else custom_id,
        )
        self.locale_str_title = title

    async def on_error(
        self,
        i: "INTERACTION",
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

    async def on_submit(self, i: "INTERACTION") -> None:
        self.validate_inputs()
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

                if item.is_digit:
                    item.placeholder = f"({item.min_value} ~ {item.max_value})"
                elif item.is_bool:
                    item.placeholder = "0/1"

                if item.locale_str_placeholder:
                    item.placeholder = translator.translate(item.locale_str_placeholder, locale)
                if item.locale_str_default:
                    item.default = translator.translate(item.locale_str_default, locale)

    def validate_inputs(self) -> None:
        """Validates all TextInput children of the modal. Raises InvalidInputError if any input is invalid."""
        for item in self.children:
            if isinstance(item, TextInput) and item.is_digit:
                try:
                    value = int(item.value)
                except ValueError as e:
                    raise InvalidInputError(
                        LocaleStr(
                            "Input `{input}` needs to be an integer",
                            key="invalid_input.input_needs_to_be_int",
                            input=item.label,
                        )
                    ) from e
                if item.max_value is not None and value > item.max_value:
                    raise InvalidInputError(
                        LocaleStr(
                            "Input `{input}` needs to be less than or equal to {max_value}",
                            key="invalid_input.input_out_of_range.max_value",
                            input=item.label,
                            max_value=item.max_value,
                        )
                    )
                if item.min_value is not None and value < item.min_value:
                    raise InvalidInputError(
                        LocaleStr(
                            "Input `{input}` needs to be greater than or equal to {min_value}",
                            key="invalid_input.input_out_of_range.min_value",
                            min_value=item.min_value,
                            input=item.label,
                        )
                    )
            elif isinstance(item, TextInput) and item.is_bool:
                if item.value not in {"0", "1"}:
                    raise InvalidInputError(
                        LocaleStr(
                            "Input `{input}` needs to be either `0` (for false) or `1` (for true)",
                            key="invalid_input.input_needs_to_be_bool",
                            input=item.label,
                        )
                    )

    def confirm_required_inputs(self) -> bool:
        """Returns True if any required TextInput is empty. False otherwise."""
        return any(
            item.required and not item.value
            for item in self.children
            if isinstance(item, TextInput)
        )
