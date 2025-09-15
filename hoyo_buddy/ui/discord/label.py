from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy.l10n import LocaleStr, translator

from .select import Select
from .text_input import TextInput

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

__all__ = ("Label",)


class Label[T](discord.ui.Label):
    def __init__(
        self,
        *,
        text: LocaleStr | str,
        component: Select | TextInput,
        description: str | LocaleStr | None = None,
    ) -> None:
        super().__init__(
            text=text if isinstance(text, str) else "#NoTrans",
            component=component,
            description=description
            if isinstance(description, str) or description is None
            else "#NoTrans",
        )

        self.locale_str_text = text
        self.locale_str_description = description
        self.component: T

    def translate(self, locale: Locale) -> None:
        self.text = translator.translate(self.locale_str_text, locale)
        if self.locale_str_description:
            self.description = translator.translate(self.locale_str_description, locale)

        if isinstance(self.component, (Select, TextInput)):
            self.component.translate(locale)
