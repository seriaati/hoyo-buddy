from typing import Tuple, Type

import discord
import genshin.errors as errors
from ambr.exceptions import DataNotFound

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQuery
from .translator import Translator
from .translator import locale_str as _T

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[
    Type[errors.GenshinException],
    Tuple[Tuple[str, str] | None, Tuple[str, str] | None],
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
    error: Exception, locale: discord.Locale, translator: Translator
) -> Tuple[ErrorEmbed, bool]:
    recognized = True
    if isinstance(error, DataNotFound):
        error = InvalidQuery()
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
            title=_T(title[0], key=title[1])
            if title
            else _T("An error occurred", key="error_title"),
            description=_T(description[0], key=description[1]) if description else str(error),
        )
    else:
        recognized = False
        embed = ErrorEmbed(
            locale,
            translator,
            title=_T("An error occurred", key="error_title"),
            description=str(error),
        )
    return embed, recognized
