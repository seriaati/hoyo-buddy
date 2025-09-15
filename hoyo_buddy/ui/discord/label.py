from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy.l10n import LocaleStr, translator

from .select import Select, SelectOption
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

    @property
    def default(self) -> str | None:
        """The default value of the underlying component."""
        if isinstance(self.component, TextInput):
            return self.component.default
        if isinstance(self.component, Select):
            return self.component.values[0] if self.component.values else None
        return None

    @default.setter
    def default(self, value: str | SelectOption | None) -> None:
        if isinstance(self.component, TextInput):
            if not isinstance(value, str) and value is not None:
                msg = "value must be a str or None for TextInput components"
                raise TypeError(msg)

            self.component.default = value

        if isinstance(self.component, Select):
            if isinstance(value, SelectOption):
                value = value.value

            for option in self.component.options:
                option.default = option.value == value

    @property
    def placeholder(self) -> str | None:
        """The placeholder of the underlying component."""
        if isinstance(self.component, TextInput):
            return self.component.placeholder
        if isinstance(self.component, Select):
            return self.component.placeholder
        return None

    @placeholder.setter
    def placeholder(self, value: str | LocaleStr | None) -> None:
        if isinstance(self.component, (TextInput, Select)):
            if isinstance(value, LocaleStr):
                self.component.locale_str_placeholder = value
            else:
                self.component.placeholder = value
        else:
            msg = "placeholder can only be set for TextInput or Select components"
            raise TypeError(msg)

    @property
    def max_value(self) -> int | None:
        """The max_value of the underlying component."""
        if isinstance(self.component, TextInput):
            return self.component.max_value
        return None

    @max_value.setter
    def max_value(self, value: int | None) -> None:
        if isinstance(self.component, TextInput):
            self.component.max_value = value
        else:
            msg = "max_value can only be set for TextInput components"
            raise TypeError(msg)

    @property
    def min_value(self) -> int | None:
        """The min_value of the underlying component."""
        if isinstance(self.component, TextInput):
            return self.component.min_value
        return None

    @min_value.setter
    def min_value(self, value: int | None) -> None:
        if isinstance(self.component, TextInput):
            self.component.min_value = value
        else:
            msg = "min_value can only be set for TextInput components"
            raise TypeError(msg)

    @property
    def value(self) -> str:
        """The value of the underlying component."""
        if isinstance(self.component, TextInput):
            return self.component.value

        if isinstance(self.component, Select):
            return self.component.values[0]

        msg = "value can only be retrieved for TextInput or Select components"
        raise TypeError(msg)
