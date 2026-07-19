from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.utils import MISSING
from loguru import logger
from seria.utils import split_list_to_chunks

from hoyo_buddy import emojis
from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import LayoutView, View

__all__ = ("BooleanSelect", "PaginatorSelect", "Select", "SelectOption", "WeekdaySelect")

MAX_OPTIONS = 25
"""Discord's limit on the number of options in a select menu."""


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


class Select[V_co: View | LayoutView](discord.ui.Select):
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
        if len(options) > MAX_OPTIONS:
            logger.warning(
                f"{self.__class__.__name__} received {len(options)} options, truncating to {MAX_OPTIONS}"
            )
            options = options[:MAX_OPTIONS]

        max_values = max(1, min(max_values, len(options)))
        min_values = min(min_values, max_values)

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


NEXT_PAGE_VALUE = "next_page"
PREV_PAGE_VALUE = "prev_page"
NAV_VALUES = frozenset({NEXT_PAGE_VALUE, PREV_PAGE_VALUE})

MAX_CARRY = 11
"""Cap on selections carried across pages, keeps every page at least 12 real options."""


def _next_page_option() -> SelectOption:
    return SelectOption(
        label=LocaleStr(key="next_page_option_label"), value=NEXT_PAGE_VALUE, emoji=emojis.FORWARD
    )


def _prev_page_option() -> SelectOption:
    return SelectOption(
        label=LocaleStr(key="prev_page_option_label"), value=PREV_PAGE_VALUE, emoji=emojis.BACK
    )


class PaginatorSelect[V_co: View | LayoutView](Select):
    """A select that paginates its options when they exceed Discord's limit of 25.

    When paginated, each page holds nav options (prev/next page), the user's current
    selections carried over from other pages (so multi-select works across pages), and a
    chunk of the full option list. Slot budget: 2 (nav) + max_values (carried, capped at
    MAX_CARRY) + page chunk = 25.
    """

    def __init__(self, options: list[SelectOption], **kwargs) -> None:
        self.options_before_split = options
        self.page_index = 0
        self._max_values: int = kwargs.pop("max_values", 1)
        super().__init__(
            options=self.process_options(), max_values=self._effective_max_values(), **kwargs
        )

        self.view: V_co

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} custom_id={self.custom_id!r} page_index={self.page_index}>"
        )

    @property
    def selected_values(self) -> list[str]:
        """`self.values` without the page-navigation values."""
        return [value for value in self.values if value not in NAV_VALUES]

    @property
    def _is_paginated(self) -> bool:
        return len(self.options_before_split) > MAX_OPTIONS

    def _effective_max_values(self) -> int:
        if self._is_paginated:
            return min(self._max_values, MAX_CARRY)
        return self._max_values

    def _page_size(self) -> int:
        return MAX_OPTIONS - 2 - self._effective_max_values()

    def _selected_options(self) -> list[SelectOption]:
        try:
            values = self.values
        except AttributeError:
            values = []
        return [
            option
            for option in self.options_before_split
            if option.default or option.value in values
        ]

    @staticmethod
    def remove_duplicate_options(
        options: list[SelectOption], existing_options: list[SelectOption]
    ) -> list[SelectOption]:
        existing_values = {option.value for option in existing_options}
        return [option for option in options if option.value not in existing_values]

    def process_options(self) -> list[SelectOption]:
        if not self._is_paginated:
            self.page_index = 0
            return list(self.options_before_split)

        pages = split_list_to_chunks(self.options_before_split, self._page_size())
        self.page_index = min(max(self.page_index, 0), len(pages) - 1)
        page = pages[self.page_index]

        carried = self.remove_duplicate_options(self._selected_options(), page)
        carried = carried[: self._effective_max_values()]

        nav: list[SelectOption] = []
        if self.page_index > 0:
            nav.append(_prev_page_option())
        if self.page_index < len(pages) - 1:
            nav.append(_next_page_option())

        return nav + carried + page

    def set_page_based_on_value(self, value: str) -> None:
        if not self._is_paginated:
            self.page_index = 0
            return

        for i, options in enumerate(
            split_list_to_chunks(self.options_before_split, self._page_size())
        ):
            if any(option.value == value for option in options):
                self.page_index = i
                return

    def update_page(self) -> bool:
        if NEXT_PAGE_VALUE in self.values:
            self.page_index += 1
        elif PREV_PAGE_VALUE in self.values:
            self.page_index -= 1
        else:
            self.translate(self.view.locale)
            return False

        selected = set(self.selected_values)
        self.options = self.process_options()
        for option in self.options:
            option.default = option.value in selected
        self.max_values = max(1, min(self._effective_max_values(), len(self.options)))

        self.translate(self.view.locale)
        return True


class BooleanSelect[V_co: View](Select):
    def __init__(self, **kwargs) -> None:
        options = [
            SelectOption(label=LocaleStr(key="yes_choice"), value="1", emoji=emojis.CHECK),
            SelectOption(label=LocaleStr(key="no_choice"), value="0", emoji=emojis.CLOSE),
        ]
        super().__init__(options=options, **kwargs)
        self.view: V_co

    @property
    def values(self) -> list[str]:
        values = super().values
        if "0" in values:
            return [""]
        return values


class WeekdaySelect[V_co: View](Select):
    def __init__(self, **kwargs) -> None:
        options = [
            SelectOption(label=LocaleStr(key="monday"), value="1"),
            SelectOption(label=LocaleStr(key="tuesday"), value="2"),
            SelectOption(label=LocaleStr(key="wednesday"), value="3"),
            SelectOption(label=LocaleStr(key="thursday"), value="4"),
            SelectOption(label=LocaleStr(key="friday"), value="5"),
            SelectOption(label=LocaleStr(key="saturday"), value="6"),
            SelectOption(label=LocaleStr(key="sunday"), value="7"),
        ]
        super().__init__(options=options, **kwargs)
        self.view: V_co
