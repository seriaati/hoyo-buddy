from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord
from seria.utils import shorten

from .l10n import translator

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale

    from .db.models import HoyoAccount
    from .l10n import LocaleStr

__all__ = ("DefaultEmbed", "Embed", "ErrorEmbed")


class Embed(discord.Embed):
    def __init__(
        self,
        locale: Locale,
        *,
        color: int | None = None,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        translated_title = translator.translate(title, locale) if title else None
        if translated_title is not None:
            translated_title = shorten(translated_title, 256)

        translated_description = translator.translate(description, locale) if description else None
        if translated_description is not None:
            translated_description = shorten(translated_description, 4096)

        super().__init__(
            color=color, title=translated_title, url=url, description=translated_description
        )
        self.locale = locale

    def __repr__(self) -> str:
        return f"<Embed title={self.title!r} description={self.description!r}>"

    def add_field(
        self, *, name: LocaleStr | str, value: LocaleStr | str | None = None, inline: bool = True
    ) -> Self:
        translated_name = translator.translate(name, self.locale)
        translated_value = translator.translate(value, self.locale) if value else ""
        return super().add_field(
            name=shorten(translated_name, 256), value=shorten(translated_value, 1024), inline=inline
        )

    def set_author(
        self, *, name: LocaleStr | str, url: str | None = None, icon_url: str | None = None
    ) -> Self:
        translated_name = translator.translate(name, self.locale)
        return super().set_author(name=shorten(translated_name, 256), url=url, icon_url=icon_url)

    def set_footer(
        self, *, text: LocaleStr | str | None = None, icon_url: str | None = None
    ) -> Self:
        translated_text = translator.translate(text, self.locale) if text else None
        return super().set_footer(text=translated_text, icon_url=icon_url)

    def add_acc_info(self, account: HoyoAccount, *, blur: bool = True) -> Self:
        """Add HoyoAccount information to the author field."""
        return self.set_author(
            name=account.blurred_display if blur else str(account), icon_url=account.game_icon
        )

    def copy(self) -> Self:
        copy = super().copy()
        copy.locale = self.locale
        return copy

    def add_description(self, description: LocaleStr | str) -> Self:
        translated_description = translator.translate(description, self.locale)
        if self.description is None:
            self.description = translated_description
        else:
            self.description += f"\n{translated_description}"
        return self

    def set_image(self, url: str | discord.File | None = None) -> Self:
        if isinstance(url, discord.File):
            url = f"attachment://{url.filename}"
        return super().set_image(url=url)


class DefaultEmbed(Embed):
    def __init__(
        self,
        locale: Locale,
        *,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        super().__init__(locale, color=6649080, title=title, url=url, description=description)


class ErrorEmbed(Embed):
    def __init__(
        self,
        locale: Locale,
        *,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        super().__init__(locale, color=15169131, title=title, url=url, description=description)
