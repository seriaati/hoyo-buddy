from __future__ import annotations

from typing import TYPE_CHECKING, Self

import discord

if TYPE_CHECKING:
    from .db.models import HoyoAccount
    from .l10n import LocaleStr, Translator

__all__ = ("DefaultEmbed", "Embed", "ErrorEmbed")


class Embed(discord.Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        color: int | None = None,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        translated_title = translator.translate(title, locale, title_case=True) if title else None
        translated_description = translator.translate(description, locale) if description else None

        super().__init__(
            color=color, title=translated_title, url=url, description=translated_description
        )
        self.locale = locale
        self.translator = translator

    def __repr__(self) -> str:
        return f"<Embed title={self.title!r} description={self.description!r}>"

    def add_field(
        self, *, name: LocaleStr | str, value: LocaleStr | str, inline: bool = True
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale, title_case=True)
        translated_value = self.translator.translate(value, self.locale)
        return super().add_field(name=translated_name, value=translated_value, inline=inline)

    def set_author(
        self, *, name: LocaleStr | str, url: str | None = None, icon_url: str | None = None
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale)
        return super().set_author(name=translated_name, url=url, icon_url=icon_url)

    def set_footer(
        self, *, text: LocaleStr | str | None = None, icon_url: str | None = None
    ) -> Self:
        translated_text = self.translator.translate(text, self.locale) if text else None
        return super().set_footer(text=translated_text, icon_url=icon_url)

    def add_acc_info(self, account: HoyoAccount, *, blur: bool = True) -> Self:
        """Add HoyoAccount information to the author field."""
        return self.set_author(
            name=account.blurred_display if blur else str(account), icon_url=account.game_icon
        )

    def copy(self) -> Self:
        copy = super().copy()
        copy.locale = self.locale
        copy.translator = self.translator
        return copy


class DefaultEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        super().__init__(
            locale, translator, color=6649080, title=title, url=url, description=description
        )


class ErrorEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: LocaleStr | str | None = None,
        url: str | None = None,
        description: LocaleStr | str | None = None,
    ) -> None:
        super().__init__(
            locale, translator, color=15169131, title=title, url=url, description=description
        )
