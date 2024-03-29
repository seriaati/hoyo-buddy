from typing import TYPE_CHECKING, Literal

from ambr.exceptions import DataNotFoundError
from genshin import errors as genshin_errors
from mihomo import errors as mihomo_errors

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQueryError
from .translator import LocaleStr, Translator

if TYPE_CHECKING:
    import discord

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[int, dict[Literal["title", "description"], LocaleStr]] = {
    -5003: {
        "title": LocaleStr("Daily check-in reward already claimed", key="already_claimed_title"),
        "description": LocaleStr("Come back tomorrow!", key="already_claimed_description"),
    },
    -100: {
        "title": LocaleStr("Invalid Cookies", key="invalid_cookies_title"),
        "description": LocaleStr(
            "Refresh your Cookies by adding your accounts again using </accounts>",
            key="invalid_cookies_description",
        ),
    },
    -3205: {
        "title": LocaleStr("Invalid verification code", key="invalid_verification_code_title"),
        "description": LocaleStr(
            "Please check the verification code and try again.",
            key="invalid_verification_code_description",
        ),
    },
    -3208: {
        "title": LocaleStr("Invalid e-mail or password", key="invalid_email_password_title"),
        "description": LocaleStr(
            "The e-mail or password you provided is incorrect. Please check and try again.",
            key="invalid_email_password_description",
        ),
    },
    -3206: {
        "title": LocaleStr(
            "Verification code service unavailable", key="verification_code_unavailable_title"
        ),
        "description": LocaleStr(
            "Please try again later.", key="verification_code_unavailable_description"
        ),
    },
}

MIHOMO_ERROR_CONVERTER: dict[
    type[mihomo_errors.BaseException],
    dict[Literal["title", "description"], LocaleStr],
] = {
    mihomo_errors.HttpRequestError: {
        "title": LocaleStr("Failed to fetch data", key="http_request_error_title"),
        "description": LocaleStr("Please try again later.", key="http_request_error_description"),
    },
    mihomo_errors.UserNotFound: {
        "title": LocaleStr("User not found", key="user_not_found_title"),
        "description": LocaleStr(
            "Please check the provided UID.", key="user_not_found_description"
        ),
    },
    mihomo_errors.InvalidParams: {
        "title": LocaleStr("Invalid parameters", key="invalid_params_title"),
        "description": LocaleStr(
            "Please check the provided parameters.", key="invalid_params_description"
        ),
    },
}


def get_error_embed(
    error: Exception, locale: "discord.Locale", translator: Translator
) -> tuple[ErrorEmbed, bool]:
    recognized = True
    embed = None

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
        title, description = None, None

        err_info = (
            GENSHIN_ERROR_CONVERTER.get(error.retcode)
            if isinstance(error, genshin_errors.GenshinException)
            else MIHOMO_ERROR_CONVERTER.get(type(error))
        )
        if err_info is not None:
            title, description = err_info["title"], err_info["description"]
            embed = ErrorEmbed(locale, translator, title=title, description=description)

    if embed is None:
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
