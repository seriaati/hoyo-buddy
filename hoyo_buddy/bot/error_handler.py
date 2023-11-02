from typing import Dict, Optional, Tuple, Type

import discord
import genshin.errors as errors

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError
from .translator import Translator
from .translator import locale_str as _T

__all__ = ("get_error_embed",)

ERROR_CONVERTER: Dict[
    Type[errors.GenshinException],
    Tuple[Optional[Tuple[str, str]], Optional[Tuple[str, str]]],
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
) -> ErrorEmbed:
    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            locale,
            translator,
            title=error.title,
            description=error.message,
        )
    elif isinstance(error, errors.GenshinException):
        title, description = ERROR_CONVERTER.get(type(error), (None, None))
        embed = ErrorEmbed(
            locale,
            translator,
            title=_T(title[0], key=title[1])
            if title
            else _T("An error occurred", key="error_title"),
            description=_T(description[0], key=description[1])
            if description
            else _T(str(error), translate=False),
        )
    else:
        embed = ErrorEmbed(
            locale,
            translator,
            title=_T("An error occurred", key="error_title"),
            description=_T(str(error), translate=False),
        )
    return embed
