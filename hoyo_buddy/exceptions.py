class HoyoBuddyError(Exception):
    def __init__(self, message: str, **kwargs) -> None:
        self.message = message
        self.kwargs = kwargs

    def __str__(self) -> str:
        return self.message
