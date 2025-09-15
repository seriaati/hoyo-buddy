from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy.l10n import LocaleStr, translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

__all__ = ("TextDisplay",)


class TextDisplay(discord.ui.TextDisplay):
    def __init__(self, *, content: LocaleStr | str) -> None:
        super().__init__(content=content if isinstance(content, str) else "#NoTrans")
        self.locale_str_content = content

    def translate(self, locale: Locale) -> None:
        self.content = translator.translate(self.locale_str_content, locale)
