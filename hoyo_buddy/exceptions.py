from __future__ import annotations

from typing import TYPE_CHECKING

from discord.app_commands.errors import AppCommandError
from discord.utils import format_dt

from .enums import Game
from .l10n import EnumStr, LocaleStr

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from .enums import ChallengeType, Platform


class HoyoBuddyError(Exception):
    def __init__(self, title: LocaleStr, message: LocaleStr | None = None) -> None:
        self.title = title
        self.message = message


class InvalidInputError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(title=LocaleStr(key="invalid_input_error_title"), message=reason)


class InvalidQueryError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="invalid_query_error_title"), message=LocaleStr(key="invalid_query_error_message")
        )


class AccountNotFoundError(HoyoBuddyError, AppCommandError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="account_not_found_error_title"),
            message=LocaleStr(key="account_not_found_error_message"),
        )


class NoAccountFoundError(HoyoBuddyError):
    def __init__(self, games: Sequence[Game] | None = None, platform: Platform | None = None) -> None:
        if platform is not None:
            message = LocaleStr(key="no_account_found_for_games_platform_error_message", platform=EnumStr(platform))
        else:
            message = LocaleStr(key="no_account_found_for_games_error_message")

        super().__init__(title=LocaleStr(key="no_account_found_for_games_error_title"), message=message)
        self.games = games or list(Game)


class CardNotReadyError(HoyoBuddyError):
    def __init__(self, character_name: str) -> None:
        super().__init__(
            title=LocaleStr(key="exceptions.card_not_ready_error.title", character_name=character_name),
            message=LocaleStr(key="exceptions.card_not_ready_error.message"),
        )


class InvalidImageURLError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="invalid_image_url_error_title"),
            message=LocaleStr(key="invalid_image_url_error_message"),
        )


class InvalidColorError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="invalid_color_error_title"), message=LocaleStr(key="invalid_color_error_message")
        )


class IncompleteParamError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(title=LocaleStr(key="incomplete_param_error_title"), message=reason)


class NSFWPromptError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="nsfw_prompt_error_title"), message=LocaleStr(key="nsfw_prompt_error_message")
        )


class NoCharsFoundError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="no_characters_found_error_title"),
            message=LocaleStr(key="no_characters_found_error_message"),
        )


class ActionInCooldownError(HoyoBuddyError):
    def __init__(self, available_time: datetime) -> None:
        super().__init__(
            title=LocaleStr(key="action_in_cooldown_error_title"),
            message=LocaleStr(key="action_in_cooldown_error_message", available_time=format_dt(available_time, "T")),
        )


class NoChallengeDataError(HoyoBuddyError):
    def __init__(self, challenge_type: ChallengeType) -> None:
        super().__init__(
            title=LocaleStr(key="no_challenge_data_err_title", challenge=EnumStr(challenge_type)),
            message=LocaleStr(key="no_challenge_data_err_message", challenge=EnumStr(challenge_type)),
        )


class AIGenImageError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="ai_gen_image_error_title"), message=LocaleStr(key="ai_gen_image_error_message")
        )


class DownloadImageFailedError(HoyoBuddyError):
    def __init__(self, url: str, status: int) -> None:
        super().__init__(
            title=LocaleStr(key="download_image_failed_error_title"),
            message=LocaleStr(key="download_image_failed_error_message", url=url, status=status),
        )


class AutocompleteNotDoneYetError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="search_autocomplete_not_setup"))


class FeatureNotImplementedError(HoyoBuddyError):
    def __init__(self, *, platform: Platform | None = None, game: Game) -> None:
        message = (
            LocaleStr(key="not_implemented_error_only_game_message", game=EnumStr(game))
            if platform is None
            else LocaleStr(key="not_implemented_error_message", game=EnumStr(game), platform=EnumStr(platform))
        )
        super().__init__(title=LocaleStr(key="not_implemented_error_title"), message=message)


class ThirdPartyCardTempError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="third_party_card_temp_error_title"),
            message=LocaleStr(key="third_party_card_temp_error_message"),
        )


class AuthkeyExtractError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="extract_authkey_error_title"), message=LocaleStr(key="extract_authkey_error_message")
        )


class InvalidFileExtError(HoyoBuddyError):
    def __init__(self, file_format: str) -> None:
        super().__init__(
            title=LocaleStr(key="gacha_upload_invalid_file_error_title"),
            message=LocaleStr(key="gacha_upload_invalid_file_error_message", file_format=file_format),
        )


class UIDMismatchError(HoyoBuddyError):
    def __init__(self, uid: int | str) -> None:
        super().__init__(
            title=LocaleStr(key="uid_mismatch_error_title"),
            message=LocaleStr(key="uid_mismatch_error_message", uid=uid),
        )


class NoGachaLogFoundError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(key="no_gacha_log_found_error_title"),
            message=LocaleStr(key="no_gacha_log_found_error_message"),
        )


class LeaderboardNotFoundError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="leaderboard_not_found"))


class NotSupportedByEnkaError(HoyoBuddyError):
    def __init__(self, game: Game) -> None:
        super().__init__(
            title=LocaleStr(key="not_supported_by_enka_error_title"),
            message=LocaleStr(key="not_supported_by_enka_error_message", game=EnumStr(game)),
        )
