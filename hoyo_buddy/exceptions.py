from .bot import locale_str


class HoyoBuddyError(Exception):
    def __init__(self, title: locale_str, message: locale_str) -> None:
        self.title = title
        self.message = message
