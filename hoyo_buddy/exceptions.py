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
