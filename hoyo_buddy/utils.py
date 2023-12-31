import datetime
from typing import TypeVar

T = TypeVar("T")


def split_list(input_list: list[T], n: int) -> list[list[T]]:
    """
    Split a list into sublists of length n

    Parameters:
        input_list: The input list
        n: The length of each sublist
    """
    if n <= 0:
        msg = "Parameter n must be a positive integer"
        raise ValueError(msg)

    return [input_list[i : i + n] for i in range(0, len(input_list), n)]


def get_now() -> datetime.datetime:
    """
    Get the current time in UTC+8
    """
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def create_bullet_list(input_list: list[str]) -> str:
    """
    Create a bullet list from a list of strings
    """
    return "\n".join(["* " + item for item in input_list])


def shorten(text: str, length: int) -> str:
    """
    Shorten a string to the specified length
    """
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."
