from __future__ import annotations

from datetime import timedelta
from typing import Literal

import discord
import genshin
from ambr.exceptions import DataNotFoundError as AmbrDataNotFoundError
from discord.utils import format_dt
from enka import errors as enka_errors
from genshin import errors as genshin_errors
from hakushin.errors import NotFoundError as HakushinNotFoundError
from yatta.exceptions import DataNotFoundError as YattaDataNotFoundError

from ..embeds import ErrorEmbed
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

GENSHIN_ERROR_CONVERTER: dict[
    tuple[int, ...], dict[Literal["title", "description", "image"], LocaleStr | str]
] = {
    (-5003,): {
        "title": LocaleStr(key="already_claimed_title"),
        "description": LocaleStr(key="already_claimed_description"),
    },
    (-100, 10001, 10103, -1071): {
        "title": LocaleStr(key="invalid_cookies_title"),
        "description": LocaleStr(key="invalid_cookies_description"),
    },
    (-3205, -3102): {
        "title": LocaleStr(key="invalid_verification_code_title"),
        "description": LocaleStr(key="invalid_verification_code_description"),
    },
    (-3208, -3203, -3004): {
        "title": LocaleStr(key="invalid_email_password_title"),
        "description": LocaleStr(key="invalid_email_password_description"),
    },
    (-3206,): {
        "title": LocaleStr(key="verification_code_unavailable_title"),
        "description": LocaleStr(key="verification_code_unavailable_description"),
    },
    (-3101, -1004): {
        "title": LocaleStr(key="action_in_cooldown_error_title"),
        "description": LocaleStr(
            key="action_in_cooldown_error_message",
            available_time=format_dt(get_now() + timedelta(minutes=1), "T"),
        ),
    },
    (-3202,): {
        "title": LocaleStr(key="account_locked_title"),
        "description": LocaleStr(key="account_locked_description"),
    },
    (10102,): {
        "title": LocaleStr(key="data_not_public.title"),
        "description": LocaleStr(key="data_not_public.description"),
        "image": "https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/DataNotPublicTutorial.gif",
    },
    (-2021, -2011): {"title": LocaleStr(key="redeem_code.ar_too_low")},
    (30001,): {
        "title": LocaleStr(key="geetest.no_need"),
        "description": LocaleStr(key="geetest.no_need.description"),
    },
    tuple(genshin.constants.GEETEST_RETCODES): {
        "title": LocaleStr(key="geetest.required"),
        "description": LocaleStr(
            geetest_type=EnumStr(GeetestType.REALTIME_NOTES), key="geetest.required.description"
        ),
    },
    (-1,): {"title": LocaleStr(key="game_maintenance_title")},
    # Below are custom retcodes for Hoyo Buddy, they don't exist in Hoyo's API
    (999,): {
        "title": LocaleStr(key="redeeem_code.cookie_token_expired_title"),
        "description": LocaleStr(key="redeeem_code.cookie_token_expired_description"),
    },
    (1000,): {
        "title": LocaleStr(key="redeeem_code.cookie_token_refresh_failed_title"),
        "description": LocaleStr(key="redeeem_code.cookie_token_refresh_failed_description"),
    },
    (-9999,): {
        "title": LocaleStr(key="geetest.required"),
        "description": LocaleStr(
            geetest_type=EnumStr(GeetestType.DAILY_CHECKIN), key="geetest.required.description"
        ),
    },
}


ENKA_ERROR_CONVERTER: dict[
    type[enka_errors.EnkaAPIError], dict[Literal["title", "description", "image"], LocaleStr]
] = {
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
}


def get_error_embed(error: Exception, locale: discord.Locale) -> tuple[ErrorEmbed, bool]:
    recognized = True
    embed = None

    if isinstance(error, ExceptionGroup):
        error = error.exceptions[0]

    if isinstance(error, AmbrDataNotFoundError | YattaDataNotFoundError | HakushinNotFoundError):
        error = InvalidQueryError()

    if isinstance(error, discord.Forbidden):
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
    elif isinstance(error, genshin_errors.GenshinException | enka_errors.EnkaAPIError):
        err_info = None

        if isinstance(error, genshin_errors.GenshinException):
            retcode = -9999 if isinstance(error, genshin.DailyGeetestTriggered) else error.retcode
            for codes, info in GENSHIN_ERROR_CONVERTER.items():
                if retcode in codes:
                    err_info = info
                    break
            if err_info is None:
                err_info = {"title": f"[{error.retcode}] HoYo API Error", "description": error.msg}
        else:
            err_info = ENKA_ERROR_CONVERTER.get(type(error))

        if err_info is not None:
            title, description, image = (
                err_info["title"],
                err_info.get("description", None),
                err_info.get("image", None),
            )
            embed = ErrorEmbed(locale, title=title, description=description)
            if image is not None:
                embed.set_image(url=image)

    if embed is None:
        recognized = False
        description = f"{type(error).__name__}: {error}" if error else type(error).__name__
        embed = ErrorEmbed(locale, title=LocaleStr(key="error_title"), description=description)

    embed.set_footer(text=LocaleStr(key="error_footer"))
    return embed, recognized
