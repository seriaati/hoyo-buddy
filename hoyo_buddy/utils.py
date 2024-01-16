import datetime
import inspect
import logging
import time
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

LOGGER_ = logging.getLogger(__name__)


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


def timer(func: "Callable[..., Any]") -> "Callable[..., Any]":
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()

        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)

        LOGGER_.debug("%s took %.6f seconds to run", func.__name__, time.time() - start)
        return result

    return wrapper


def try_except(func: "Callable") -> "Callable":
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)
        except Exception as e:
            LOGGER_.exception("Error in %s", func.__name__)
            raise e from None

    return wrapper
