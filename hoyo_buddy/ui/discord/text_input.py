from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.utils import MISSING

from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

__all__ = ("TextInput",)


class TextInput(discord.ui.TextInput):
    def __init__(
        self,
        *,
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
    ) -> None:
        super().__init__(
            style=style,
            custom_id=custom_id,
            required=required,
            min_length=min_length,
            max_length=max_length,
            row=row,
        )
        self.locale_str_placeholder = placeholder
        self.locale_str_default = default

        self.is_digit = is_digit
        self.max_value = max_value
        self.min_value = min_value

    def translate(self, locale: Locale) -> None:
        if self.is_digit:
            self.placeholder = f"({self.min_value} ~ {self.max_value})"

        if self.locale_str_placeholder:
            self.placeholder = translator.translate(self.locale_str_placeholder, locale)
        if self.locale_str_default:
            self.default = translator.translate(self.locale_str_default, locale)
