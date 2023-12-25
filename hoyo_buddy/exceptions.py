from discord.app_commands.errors import AppCommandError

from .bot.translator import LocaleStr


class HoyoBuddyError(Exception):
    def __init__(self, title: LocaleStr, message: LocaleStr) -> None:
        self.title = title
        self.message = message


class InvalidInputError(HoyoBuddyError):
    def __init__(self, reason: LocaleStr) -> None:
        super().__init__(
            title=LocaleStr("Invalid input", key="invalid_input_error_title"),
            message=reason,
        )


class InvalidQueryError(HoyoBuddyError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Invalid query", key="invalid_query_error_title"),
            message=LocaleStr(
                "Unable to find anything with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="invalid_query_error_message",
            ),
        )


class AccountNotFoundError(HoyoBuddyError, AppCommandError):
    def __init__(self) -> None:
        super().__init__(
            title=LocaleStr("Account not found", key="account_not_found_error_title"),
            message=LocaleStr(
                "Unable to find an account with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="account_not_found_error_message",
            ),
        )
