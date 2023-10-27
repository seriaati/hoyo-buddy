from typing import Optional, Self

import discord
from discord.app_commands import locale_str

from ..bot import HoyoBuddy
from ..bot.translator import Translator
from ..db.models import User
from ..exceptions import HoyoBuddyError


class Embed(discord.Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        color: Optional[int] = None,
        title: Optional[locale_str] = None,
        url: Optional[str] = None,
        description: Optional[locale_str] = None,
    ):
        translated_title = translator.translate(title, locale) if title else None
        translated_description = (
            translator.translate(description, locale) if description else None
        )

        super().__init__(
            color=color,
            title=translated_title,
            url=url,
            description=translated_description,
        )
        self.locale = locale
        self.translator = translator

    def add_field(
        self,
        *,
        name: locale_str,
        value: locale_str,
        inline: bool = True,
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale)
        translated_value = self.translator.translate(value, self.locale)
        return super().add_field(
            name=translated_name, value=translated_value, inline=inline
        )

    def set_author(
        self,
        *,
        name: locale_str,
        url: Optional[str] = None,
        icon_url: Optional[str] = None,
    ) -> Self:
        translated_name = self.translator.translate(name, self.locale)
        return super().set_author(name=translated_name, url=url, icon_url=icon_url)

    def set_footer(
        self,
        *,
        text: Optional[locale_str] = None,
        icon_url: Optional[str] = None,
    ) -> Self:
        translated_text = self.translator.translate(text, self.locale) if text else None
        return super().set_footer(text=translated_text, icon_url=icon_url)


class DefaultEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: Optional[locale_str] = None,
        url: Optional[str] = None,
        description: Optional[locale_str] = None,
    ):
        super().__init__(
            locale,
            translator,
            color=6649080,
            title=title,
            url=url,
            description=description,
        )


class ErrorEmbed(Embed):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        title: Optional[locale_str] = None,
        url: Optional[str] = None,
        description: Optional[locale_str] = None,
    ):
        super().__init__(
            locale,
            translator,
            color=15169131,
            title=title,
            url=url,
            description=description,
        )


async def get_error_embed(
    i: discord.Interaction[HoyoBuddy], error: Exception
) -> ErrorEmbed:
    user = await User.get(id=i.user.id).prefetch_related("settings")

    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            user.settings.locale or i.locale,
            i.client.translator,
            title=locale_str("An error occurred", key="error_title", **error.kwargs),
            description=locale_str(str(error), key=error.key, **error.kwargs),
        )
    else:
        embed = ErrorEmbed(
            user.settings.locale or i.locale,
            i.client.translator,
            title=locale_str("An error occurred", key="error_title"),
            description=locale_str(str(error), translate=False),
        )
    return embed
