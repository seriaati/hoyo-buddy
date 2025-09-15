from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.utils import MISSING
from seria.utils import split_list_to_chunks

from hoyo_buddy import emojis
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import View

__all__ = ("PaginatorSelect", "Select", "SelectOption")


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
            label=label if isinstance(label, str) else label.identifier,
            value=value,
            emoji=emoji,
            default=default,
        )
        self.locale_str_label = label
        self.locale_str_description = description


class Select[V_co: View](discord.ui.Select):
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
        if not options:
            options = [SelectOption(label="placeholder", value="0")]
            disabled = True
        super().__init__(
            custom_id=custom_id,
            min_values=min_values,
            max_values=max_values,
            options=options,  # pyright: ignore[reportArgumentType]
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
        return self._underlying.options  # pyright: ignore [reportReturnType]

    @options.setter
    def options(self, value: list[SelectOption]) -> None:
        if not value:
            value = [SelectOption(label="placeholder", value="0")]
            self.disabled = True
        self._underlying.options = value  # pyright: ignore [reportAttributeAccessIssue]

    def translate(self, locale: Locale) -> None:
        if self.locale_str_placeholder:
            self.placeholder = translator.translate(self.locale_str_placeholder, locale)[:100]
        for option in self.options:
            # NOTE: This is a workaround for a bug(?) in discord.py where options somehow get converted to discord.components.SelectOption internally
            if not isinstance(option, SelectOption):  # pyright: ignore[reportUnnecessaryIsInstance]
                continue

            option.label = translator.translate(option.locale_str_label, locale)[:100]
            option.value = option.value[:100]

            if option.locale_str_description:
                option.description = translator.translate(option.locale_str_description, locale)[
                    :100
                ]

    async def set_loading_state(self, i: Interaction) -> None:
        self.original_options = self.options.copy()
        self.original_disabled = self.disabled
        self.original_placeholder = self.placeholder[:] if self.placeholder else None
        self.original_max_values = self.max_values
        self.original_min_values = self.min_values

        self.view.disable_items()

        self.options = [
            SelectOption(
                label=translator.translate(LocaleStr(key="loading_text"), self.view.locale),
                value="loading",
                default=True,
                emoji=emojis.LOADING,
            )
        ]
        self.disabled = True
        self.max_values = 1
        self.min_values = 1

        await self.view.absolute_edit(i, view=self.view)

    async def unset_loading_state(self, i: Interaction, **kwargs) -> None:
        if (
            not self.original_options
            or self.original_disabled is None
            or self.original_max_values is None
            or self.original_min_values is None
        ):
            msg = "unset_loading_state called before set_loading_state"
            raise RuntimeError(msg)

        self.view.enable_items()

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

    def reset_options_defaults(self) -> None:
        for option in self.options:
            option.default = False


NEXT_PAGE = SelectOption(
    label=LocaleStr(key="next_page_option_label"), value="next_page", emoji=emojis.FORWARD
)
PREV_PAGE = SelectOption(
    label=LocaleStr(key="prev_page_option_label"), value="prev_page", emoji=emojis.BACK
)


class PaginatorSelect[V_co: View](Select):
    def __init__(self, options: list[SelectOption], **kwargs) -> None:
        if not options:
            options = [SelectOption(label="placeholder", value="0")]
            kwargs["disabled"] = True

        self.options_before_split = options
        self.page_index = 0
        self._max_values = kwargs.get("max_values", 1)
        super().__init__(options=self.process_options(), **kwargs)

        self.view: V_co

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} custom_id={self.custom_id!r} page_index={self.page_index}>"
        )

    @staticmethod
    def remove_duplicate_options(
        options: list[SelectOption], existing_options: list[SelectOption]
    ) -> list[SelectOption]:
        existing_values = {option.value for option in existing_options}
        return [option for option in options if option.value not in existing_values]

    def process_options(self) -> list[SelectOption]:
        split_options = split_list_to_chunks(self.options_before_split, 23 - self._max_values)
        if not split_options:
            return []

        try:
            values = self.values
        except AttributeError:
            values = []

        selected_options = [
            option
            for option in self.options_before_split
            if option.value in values and option.value not in {NEXT_PAGE.value, PREV_PAGE.value}
        ]

        try:
            split_options[self.page_index]
        except IndexError:
            self.page_index = 0

        if self.page_index == 0:
            if len(split_options) == 1:
                return split_options[0]
            selected_options = self.remove_duplicate_options(selected_options, split_options[0])
            return [NEXT_PAGE] + selected_options + split_options[0]

        if self.page_index == len(split_options) - 1:
            selected_options = self.remove_duplicate_options(selected_options, split_options[-1])
            return [PREV_PAGE] + selected_options + split_options[-1]

        selected_options = self.remove_duplicate_options(
            selected_options, split_options[self.page_index]
        )
        return [PREV_PAGE] + [NEXT_PAGE] + selected_options + split_options[self.page_index]

    def set_page_based_on_value(self, value: str) -> None:
        split_options = split_list_to_chunks(self.options_before_split, 23)

        for i, options in enumerate(split_options):
            if value in [option.value for option in options]:
                self.page_index = i
                break

    def update_page(self) -> bool:
        changed = False
        if "next_page" in self.values:
            changed = True
            self.page_index += 1
            self.options = self.process_options()
        elif "prev_page" in self.values:
            changed = True
            self.page_index -= 1
            self.options = self.process_options()

        if changed:
            for option in self.options:
                option.default = False
            self.update_options_defaults()

            for option in self.options:
                if option.value in {PREV_PAGE.value, NEXT_PAGE.value}:
                    option.default = False

            self.max_values = min(self._max_values, len(self.options))

        self.translate(self.view.locale)
        return changed


class BooleanSelect[V_co: View](Select):
    def __init__(self, **kwargs) -> None:
        options = [
            SelectOption(label=LocaleStr(key="yes_choice"), value="1", emoji=emojis.CHECK),
            SelectOption(label=LocaleStr(key="no_choice"), value="0", emoji=emojis.CLOSE),
        ]
        super().__init__(options=options, **kwargs)
        self.view: V_co
