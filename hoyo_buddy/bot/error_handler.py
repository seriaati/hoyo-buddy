from __future__ import annotations

from datetime import timedelta
from typing import Literal

import discord
from ambr.exceptions import DataNotFoundError as AmbrDataNotFoundError
from discord.utils import format_dt
from enka import errors as enka_errors
from genshin import errors as ge
from hakushin.errors import NotFoundError as HakushinNotFoundError
from yatta.exceptions import DataNotFoundError as YattaDataNotFoundError

from ..embeds import DefaultEmbed, ErrorEmbed
from ..emojis import get_game_emoji
from ..enums import GeetestType
from ..exceptions import (
    BlockedByAutoModError,
    HoyoBuddyError,
    InvalidQueryError,
    MissingPermissionsError,
    NoAccountFoundError,
)
from ..l10n import EnumStr, LocaleStr
from ..utils import get_now

__all__ = ("get_error_embed",)

type ErrorInfo = dict[Literal["title", "description", "image"], LocaleStr | str]


GPY_ERRORS: dict[
    type[ge.GenshinException] | tuple[type[ge.GenshinException], ...] | int, ErrorInfo
] = {
    ge.RedemptionClaimed: {"title": LocaleStr(key="gift_code_redeemed")},
    ge.AlreadyClaimed: {
        "title": LocaleStr(key="already_claimed_title"),
        "description": LocaleStr(key="already_claimed_description"),
    },
    ge.InvalidCookies: {
        "title": LocaleStr(key="invalid_cookies_title"),
        "description": LocaleStr(key="invalid_cookies_description"),
    },
    ge.WrongOTP: {
        "title": LocaleStr(key="invalid_verification_code_title"),
        "description": LocaleStr(key="invalid_verification_code_description"),
    },
    (ge.AccountDoesNotExist, ge.AccountLoginFail): {
        "title": LocaleStr(key="invalid_email_password_title"),
        "description": LocaleStr(key="invalid_email_password_description"),
    },
    ge.VerificationCodeRateLimited: {
        "title": LocaleStr(key="verification_code_unavailable_title"),
        "description": LocaleStr(key="verification_code_unavailable_description"),
    },
    ge.ActionInCooldown: {
        "title": LocaleStr(key="action_in_cooldown_error_title"),
        "description": LocaleStr(
            key="action_in_cooldown_error_message",
            available_time=format_dt(get_now() + timedelta(minutes=1), "T"),
        ),
    },
    ge.AccountHasLocked: {
        "title": LocaleStr(key="account_locked_title"),
        "description": LocaleStr(key="account_locked_description"),
    },
    ge.DataNotPublic: {
        "title": LocaleStr(key="data_not_public.title"),
        "description": LocaleStr(key="data_not_public.description"),
        "image": "https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/DataNotPublicTutorial.gif",
    },
    ge.RedeemGameLevelTooLow: {"title": LocaleStr(key="redeem_code.ar_too_low")},
    ge.NoNeedGeetest: {
        "title": LocaleStr(key="geetest.no_need"),
        "description": LocaleStr(key="geetest.no_need.description"),
    },
    ge.GeetestError: {
        "title": LocaleStr(key="geetest.required"),
        "description": LocaleStr(
            geetest_type=EnumStr(GeetestType.REALTIME_NOTES), key="geetest.required.description"
        ),
    },
    ge.InternalDatabaseError: {"title": LocaleStr(key="game_maintenance_title")},
    ge.DailyGeetestTriggered: {
        "title": LocaleStr(key="geetest.required"),
        "description": LocaleStr(
            geetest_type=EnumStr(GeetestType.DAILY_CHECKIN), key="geetest.required.description"
        ),
    },
    # Below are custom retcodes for Hoyo Buddy, they don't exist in Hoyo's API
    999: {
        "title": LocaleStr(key="redeeem_code.cookie_token_expired_title"),
        "description": LocaleStr(key="redeeem_code.cookie_token_expired_description"),
    },
    1000: {
        "title": LocaleStr(key="redeeem_code.cookie_token_refresh_failed_title"),
        "description": LocaleStr(key="redeeem_code.cookie_token_refresh_failed_description"),
    },
}


ENKA_ERRORS: dict[type[enka_errors.EnkaAPIError], ErrorInfo] = {
    enka_errors.PlayerDoesNotExistError: {
        "title": LocaleStr(key="player_not_found_title"),
        "description": LocaleStr(key="player_not_found_description"),
    },
    enka_errors.GameMaintenanceError: {
        "title": LocaleStr(key="game_maintenance_title"),
        "description": LocaleStr(key="game_maintenance_description"),
    },
    enka_errors.WrongUIDFormatError: {
        "title": LocaleStr(key="invalid_uid_format_title"),
        "description": LocaleStr(key="invalid_uid_format_description"),
    },
    enka_errors.APIRequestTimeoutError: {
        "title": LocaleStr(key="api_request_timeout_title"),
        "description": LocaleStr(key="api_request_timeout_description"),
    },
}


def _get_gpy_error_info(error: ge.GenshinException) -> ErrorInfo:
    for exc_type, info in GPY_ERRORS.items():
        if isinstance(exc_type, int) and error.retcode == exc_type:
            return info

        if isinstance(exc_type, tuple):
            for et in exc_type:
                if isinstance(error, et):
                    return info

        if isinstance(exc_type, type) and isinstance(error, exc_type):
            return info

    return {"title": f"[{error.retcode}] HoYo API Error", "description": error.msg}


def get_error_embed(
    error: Exception, locale: discord.Locale
) -> tuple[ErrorEmbed | DefaultEmbed, bool]:
    recognized = True
    embed = None
    embed_type: Literal["error", "default"] = "error"

    if isinstance(error, ExceptionGroup):
        error = error.exceptions[0]

    if isinstance(error, AmbrDataNotFoundError | YattaDataNotFoundError | HakushinNotFoundError):
        error = InvalidQueryError()

    if isinstance(error, discord.HTTPException):
        if error.code == 50013:
            error = MissingPermissionsError()
        elif error.code == 200000:
            error = BlockedByAutoModError()

    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(locale, title=error.title, description=error.message)
        if isinstance(error, NoAccountFoundError):
            game_strs = [
                f"- {get_game_emoji(game)} {EnumStr(game).translate(locale)}"
                for game in error.games
            ]
            joined_str = "\n".join(game_strs)
            embed.add_description(joined_str)
    elif isinstance(error, ge.GenshinException | enka_errors.EnkaAPIError):
        err_info = None

        if isinstance(error, ge.GenshinException):
            err_info = _get_gpy_error_info(error)

            if isinstance(error, ge.VisitsTooFrequently):
                # Set as not recognized to get traceback in Sentry
                recognized = False

            if isinstance(error, ge.AlreadyClaimed):
                embed_type = "default"
        else:
            err_info = ENKA_ERRORS.get(type(error))

        if err_info is not None:
            title, description, image = (
                err_info["title"],
                err_info.get("description", None),
                err_info.get("image", None),
            )
            if embed_type == "default":
                embed = DefaultEmbed(locale, title=title, description=description)
            else:
                embed = ErrorEmbed(locale, title=title, description=description)

            if image is not None:
                embed.set_image(url=image)

    if embed is None:
        recognized = False
        description = f"{type(error).__name__}: {error}" if error else type(error).__name__
        if embed_type == "default":
            embed = DefaultEmbed(
                locale, title=LocaleStr(key="error_title"), description=description
            )
        else:
            embed = ErrorEmbed(locale, title=LocaleStr(key="error_title"), description=description)

    if embed_type == "error":
        embed.set_footer(text=LocaleStr(key="error_footer"))
    return embed, recognized
