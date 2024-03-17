from typing import TYPE_CHECKING

from ambr.exceptions import DataNotFoundError
from genshin import errors as genshin_errors
from mihomo import errors as mihomo_errors

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQueryError
from .translator import LocaleStr, Translator

if TYPE_CHECKING:
    import discord

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[
    type[genshin_errors.GenshinException],
    tuple[tuple[str, str] | None, tuple[str, str] | None],
] = {
    genshin_errors.AlreadyClaimed: (
        ("Daily check-in reward already claimed", "already_claimed_title"),
        ("Come back tomorrow!", "already_claimed_description"),
    ),
    genshin_errors.InvalidCookies: (
        ("Invalid Cookies", "invalid_cookies_title"),
        (
            "Refresh your Cookies by add your accounts again using </accounts>",
            "invalid_cookies_description",
        ),
    ),
}

MIHOMO_ERROR_CONVERTER: dict[
    type[mihomo_errors.BaseException],
    tuple[tuple[str, str] | None, tuple[str, str] | None],
] = {
    mihomo_errors.HttpRequestError: (
        ("Failed to fetch data", "http_request_error_title"),
        ("Please try again later.", "http_request_error_description"),
    ),
    mihomo_errors.UserNotFound: (
        ("User not found", "user_not_found_title"),
        ("Please check the provided UID.", "user_not_found_description"),
    ),
    mihomo_errors.InvalidParams: (
        ("Invalid parameters", "invalid_params_title"),
        ("Please check the provided parameters.", "invalid_params_description"),
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
    elif isinstance(error, genshin_errors.GenshinException | mihomo_errors.BaseException):
        if isinstance(error, genshin_errors.GenshinException):
            title, description = GENSHIN_ERROR_CONVERTER.get(type(error), (None, None))
        else:
            title, description = MIHOMO_ERROR_CONVERTER.get(type(error), (None, None))
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
        description = f"{type(error).__name__}: {error}" if error else type(error).__name__
        embed = ErrorEmbed(
            locale,
            translator,
            title=LocaleStr("An error occurred", key="error_title"),
            description=description,
        )
        embed.set_footer(
            text=LocaleStr(
                "Please report this error to the developer via /feedback", key="error_footer"
            )
        )
    return embed, recognized
