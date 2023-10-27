class HoyoBuddyError(Exception):
    def __init__(self, message: str, key: str, **kwargs) -> None:
        self.message = message
        self.kwargs = kwargs
        self.key = key

    def __str__(self) -> str:
        return self.message
