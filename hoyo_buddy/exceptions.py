from .bot.translator import locale_str as _T


class HoyoBuddyError(Exception):
    def __init__(self, title: _T, message: _T):
        self.title = title
        self.message = message
