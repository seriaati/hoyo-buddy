from typing import TYPE_CHECKING

from ambr.exceptions import DataNotFoundError
from genshin import errors

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQueryError
from .translator import LocaleStr, Translator

if TYPE_CHECKING:
    import discord

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[
    type[errors.GenshinException],
    tuple[tuple[str, str] | None, tuple[str, str] | None],
] = {
    errors.AlreadyClaimed: (
        ("Daily check-in reward already claimed", "already_claimed_title"),
        ("Come back tomorrow!", "already_claimed_description"),
    ),
    errors.InvalidCookies: (
        ("Invalid Cookies", "invalid_cookies_title"),
        (
            "Refresh your Cookies by adding your accounts again using </accounts>",
            "invalid_cookies_description",
        ),
    ),
}


def get_error_embed(
    error: Exception, locale: "discord.Locale", translator: Translator
) -> tuple[ErrorEmbed, bool]:
    recognized = True
    if isinstance(error, DataNotFoundError):
        error = InvalidQueryError()
    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            locale,
            translator,
            title=error.title,
            description=error.message,
        )
    elif isinstance(error, errors.GenshinException):
        title, description = GENSHIN_ERROR_CONVERTER.get(type(error), (None, None))
        embed = ErrorEmbed(
            locale,
            translator,
            title=LocaleStr(title[0], key=title[1])
            if title
            else LocaleStr("An error occurred", key="error_title"),
            description=LocaleStr(description[0], key=description[1])
            if description
            else str(error),
        )
    else:
        recognized = False
        embed = ErrorEmbed(
            locale,
            translator,
            title=LocaleStr("An error occurred", key="error_title"),
            description=str(error),
        )
    return embed, recognized
