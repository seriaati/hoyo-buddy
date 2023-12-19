from .bot.translator import locale_str as _T


class HoyoBuddyError(Exception):
    def __init__(self, title: _T, message: _T):
        self.title = title
        self.message = message


class InvalidInput(HoyoBuddyError):
    def __init__(self, reason: _T):
        super().__init__(
            title=_T("Invalid input", key="invalid_input_error_title"),
            message=reason,
        )


class InvalidQuery(HoyoBuddyError):
    def __init__(self):
        super().__init__(
            title=_T("Invalid query", key="invalid_query_error_title"),
            message=_T(
                "Unable to find anything with the provided query, please select choices from the autocomplete instead of typing your own query.",
                key="invalid_query_error_message",
            ),
        )
