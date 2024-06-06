from __future__ import annotations

from typing import TYPE_CHECKING

from discord.app_commands.errors import AppCommandError
from discord.utils import format_dt

from .bot.translator import LocaleStr

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from .enums import Game, Platform


class HoyoBuddyError(Exception):
    def __init__(self, title: LocaleStr, message: LocaleStr | None = None) -> None:
        self.title = title
        self.message = message


class InvalidInputError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(
            title=LocaleStr("Invalid Input", key="invalid_input_error_title"),
            message=reason,
        )


class InvalidQueryError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid Query", key="invalid_query_error_title"),
            message=LocaleStr(
                "Unable to find anything with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="invalid_query_error_message",
            ),
        )


class AccountNotFoundError(HoyoBuddyError, AppCommandError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Account Not Found", key="account_not_found_error_title"),
            message=LocaleStr(
                "Unable to find an account with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="account_not_found_error_message",
            ),
        )


class NoAccountFoundError(HoyoBuddyError):
    def __init__(self, games: Sequence[Game], platforms: Sequence[Platform]) -> None:
        title = LocaleStr("No Account Found", key="no_account_found_for_games_error_title")
        message = LocaleStr(
            "You don't have any accounts for games `{games}` and platforms `{platforms}` yet. Add one with </accounts>",
            key="no_account_found_for_games_error_message",
            games=[LocaleStr(game.value, warn_no_key=False) for game in games],
            platforms=[LocaleStr(platform.value, warn_no_key=False) for platform in platforms],
        )
        super().__init__(title=title, message=message)


class CardNotReadyError(HoyoBuddyError):
    def __init__(self, character_name: str) -> None:
        super().__init__(
            title=LocaleStr(
                "Card Data for {character_name} is not Ready Yet.",
                key="exceptions.card_not_ready_error.title",
                character_name=character_name,
            ),
            message=LocaleStr(
                (
                    "When new characters are released, I need to spend time to gather fanarts and optimize colors for their cards.\n"
                    "If you'd like to speed up this process, you can contribute to the card data by reaching me in the [Discord Server](https://dsc.gg/hoyo-buddy)."
                ),
                key="exceptions.card_not_ready_error.message",
            ),
        )


class InvalidImageURLError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid Image URL", key="invalid_image_url_error_title"),
            message=LocaleStr(
                "A valid image URL needs to be a direct URL to an image file that contains an image extension, and is publicly accessible.",
                key="invalid_image_url_error_message",
            ),
        )


class InvalidColorError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid Color", key="invalid_color_error_title"),
            message=LocaleStr(
                "A valid color needs to be a hexadecimal color code, e.g. #FF0000",
                key="invalid_color_error_message",
            ),
        )


class IncompleteParamError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(
            title=LocaleStr(
                "The Given Command Parameters are Incomplete", key="incomplete_param_error_title"
            ),
            message=reason,
        )


class NSFWPromptError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("NSFW Prompt Detected", key="nsfw_prompt_error_title"),
            message=LocaleStr(
                "The prompt contains NSFW content, please try again with a different prompt.",
                key="nsfw_prompt_error_message",
            ),
        )


class GuildOnlyFeatureError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Guild Only Feature", key="guild_only_feature_error_title"),
            message=LocaleStr(
                "This feature is only available in guilds, please try again in a guild.",
                key="guild_only_feature_error_message",
            ),
        )


class NoCharsFoundError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(
                "No Characters Found With the Selected Filter",
                key="no_characters_found_error_title",
            ),
            message=LocaleStr(
                "Please try again with a different filter",
                key="no_characters_found_error_message",
            ),
        )


class ActionInCooldownError(HoyoBuddyError):
    def __init__(self, available_time: datetime) -> None:
        super().__init__(
            title=LocaleStr("Action in Cooldown", key="action_in_cooldown_error_title"),
            message=LocaleStr(
                "Please try again at {available_time}.",
                key="action_in_cooldown_error_message",
                available_time=format_dt(available_time, "T"),
            ),
        )


class NoAbyssDataError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("No Spiral Abyss Data", key="no_abyss_data_error_title"),
            message=LocaleStr(
                "Unable to find any spiral abyss data, either you haven't started the spiral abyss yet or the data is not ready yet. Please try again later",
                key="no_abyss_data_error_message",
            ),
        )


class NoGameAccountsError(HoyoBuddyError):
    def __init__(self, platform: Platform) -> None:
        super().__init__(
            title=LocaleStr("No Game Accounts", key="no_game_accounts_error_title"),
            message=LocaleStr(
                "This {platform} account has no game accounts.",
                key="no_game_accounts_error_message",
                platform=LocaleStr(platform.value, warn_no_key=False),
            ),
        )


class TryOtherMethodError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid Cookies", key="try_other_method_error_title"),
            message=LocaleStr(
                "Please try other methods to login.\n"
                "If you are entering cookies manually through DevTools, make sure you are copying them correctly.",
                key="try_other_method_error_message",
            ),
        )


class AIGenImageError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(
                "An Error Occured While Generating Art With AI",
                key="ai_gen_image_error_title",
            ),
            message=LocaleStr("Check your prompt and try again.", key="ai_gen_image_error_message"),
        )


class DownloadImageFailedError(HoyoBuddyError):
    def __init__(self, url: str, status: int) -> None:
        super().__init__(
            title=LocaleStr("Image Download Failed", key="download_image_failed_error_title"),
            message=LocaleStr(
                "Unable to download image {url} with status code {status}.\n"
                "Try again later, try with a different image, or check if the image URL is valid.",
                key="download_image_failed_error_message",
                url=url,
                status=status,
            ),
        )


class AutocompleteNotDoneYetError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr(
                "Search autocomplete choices not set up yet, please try again later.",
                key="search_autocomplete_not_setup",
            ),
        )
