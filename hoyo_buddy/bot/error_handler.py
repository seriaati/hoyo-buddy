from datetime import timedelta
from typing import TYPE_CHECKING, Literal

from ambr.exceptions import DataNotFoundError as AmbrDataNotFoundError
from discord.utils import format_dt
from enka import errors as enka_errors
from genshin import errors as genshin_errors
from mihomo import errors as mihomo_errors
from yatta.exceptions import DataNotFoundError as YattaDataNotFoundError

from ..embeds import ErrorEmbed
from ..exceptions import HoyoBuddyError, InvalidQueryError
from ..utils import get_now
from .translator import LocaleStr, Translator

if TYPE_CHECKING:
    import discord

__all__ = ("get_error_embed",)

GENSHIN_ERROR_CONVERTER: dict[tuple[int, ...], dict[Literal["title", "description"], LocaleStr]] = {
    (-5003,): {
        "title": LocaleStr("Daily Check-In Reward Already Claimed", key="already_claimed_title"),
        "description": LocaleStr("Come back tomorrow!", key="already_claimed_description"),
    },
    (-100, 10001, 10103, -1071): {
        "title": LocaleStr("Invalid Cookies", key="invalid_cookies_title"),
        "description": LocaleStr(
            "Refresh your cookies by adding your accounts again using </accounts>",
            key="invalid_cookies_description",
        ),
    },
    (-3205, -3102): {
        "title": LocaleStr("Invalid Verification Code", key="invalid_verification_code_title"),
        "description": LocaleStr(
            "Please check the verification code and try again.",
            key="invalid_verification_code_description",
        ),
    },
    (-3208,): {
        "title": LocaleStr("Invalid Email or Password", key="invalid_email_password_title"),
        "description": LocaleStr(
            "The email or password you provided is incorrect, please check and try again.",
            key="invalid_email_password_description",
        ),
    },
    (-3206,): {
        "title": LocaleStr(
            "Verification Code Service Unavailable", key="verification_code_unavailable_title"
        ),
        "description": LocaleStr(
            "Please try again later", key="verification_code_unavailable_description"
        ),
    },
    (-3101, -1004): {
        "title": LocaleStr("Action in Cooldown", key="action_in_cooldown_error_title"),
        "description": LocaleStr(
            "You are currently in cooldown, please try again at {available_time}.",
            key="action_in_cooldown_error_message",
            available_time=format_dt(get_now() + timedelta(minutes=1), "T"),
        ),
    },
    (-2017, -2018): {
        "title": LocaleStr("Redemption code already claimed", key="redeem_code.already_claimed")
    },
    (-2001,): {
        "title": LocaleStr("Redemption code expired", key="redeem_code.expired"),
    },
    (-1065, -2003, -2004, -2014): {
        "title": LocaleStr("Invalid redemption code", key="redeem_code.invalid"),
    },
    (-2016,): {
        "title": LocaleStr("Code redemption in cooldown", key="redeem_code.cooldown"),
    },
    (-2021,): {
        "title": LocaleStr("Adventure rank too low (less than 10)", key="redeem_code.ar_too_low"),
    },
    # 999 and 1000 are custom retcodes for Hoyo Buddy, they don't exist in Hoyo's API
    (999,): {
        "title": LocaleStr("Cookie Token Expired", key="redeeem_code.cookie_token_expired_title"),
        "description": LocaleStr(
            "Refresh your cookie token by adding your accounts again using </accounts>.\n"
            "If you use the email and password method to add your accounts, cookie token can be refreshed automatically.",
            key="redeeem_code.cookie_token_expired_description",
        ),
    },
    (1000,): {
        "title": LocaleStr(
            "Failed to Refresh Cookie Token", key="redeeem_code.cookie_token_refresh_failed_title"
        ),
        "description": LocaleStr(
            "It is likely that you have changed your account's password since the last time you add your accounts.\n"
            "Please add your accounts again using </accounts> with the email and password method.",
            key="redeeem_code.cookie_token_refresh_failed_description",
        ),
    },
}

MIHOMO_ERROR_CONVERTER: dict[
    type[mihomo_errors.BaseException],
    dict[Literal["title", "description"], LocaleStr],
] = {
    mihomo_errors.HttpRequestError: {
        "title": LocaleStr("Failed to Fetch Data", key="http_request_error_title"),
        "description": LocaleStr("Please try again later", key="http_request_error_description"),
    },
    mihomo_errors.UserNotFound: {
        "title": LocaleStr("User Not Found", key="user_not_found_title"),
        "description": LocaleStr("Please check the provided UID", key="user_not_found_description"),
    },
    mihomo_errors.InvalidParams: {
        "title": LocaleStr("Invalid Parameters", key="invalid_params_title"),
        "description": LocaleStr(
            "Please check the provided parameters", key="invalid_params_description"
        ),
    },
}

ENKA_ERROR_CONVERTER: dict[
    type[enka_errors.EnkaAPIError],
    dict[Literal["title", "description"], LocaleStr],
] = {
    enka_errors.PlayerDoesNotExistError: {
        "title": LocaleStr("Player Does Not Exist", key="player_not_found_title"),
        "description": LocaleStr(
            "Please check the provided UID", key="player_not_found_description"
        ),
    },
    enka_errors.GameMaintenanceError: {
        "title": LocaleStr("Game is Under Maintenance", key="game_maintenance_title"),
        "description": LocaleStr("Please try again later", key="game_maintenance_description"),
    },
}


def get_error_embed(
    error: Exception, locale: "discord.Locale", translator: Translator
) -> tuple[ErrorEmbed, bool]:
    recognized = True
    embed = None

    if isinstance(error, AmbrDataNotFoundError | YattaDataNotFoundError):
        error = InvalidQueryError()

    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            locale,
            translator,
            title=error.title,
            description=error.message,
        )
    elif isinstance(
        error,
        genshin_errors.GenshinException | mihomo_errors.BaseException | enka_errors.EnkaAPIError,
    ):
        err_info = None

        if isinstance(error, genshin_errors.GenshinException):
            for codes, info in GENSHIN_ERROR_CONVERTER.items():
                if error.retcode in codes:
                    err_info = info
                    break
        elif isinstance(error, mihomo_errors.BaseException):
            err_info = MIHOMO_ERROR_CONVERTER.get(type(error))
        elif isinstance(error, enka_errors.EnkaAPIError):
            err_info = ENKA_ERROR_CONVERTER.get(type(error))

        if err_info is not None:
            title, description = err_info["title"], err_info.get("description", None)
            embed = ErrorEmbed(locale, translator, title=title, description=description)

    if embed is None:
        recognized = False
        description = f"{type(error).__name__}: {error}" if error else type(error).__name__
        embed = ErrorEmbed(
            locale,
            translator,
            title=LocaleStr("An Error Occurred", key="error_title"),
            description=description,
        )
        embed.set_footer(
            text=LocaleStr(
                "Please report this error to the developer via /feedback", key="error_footer"
            )
        )

    return embed, recognized
