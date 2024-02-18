import datetime
import logging
import time
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")

LOGGER_ = logging.getLogger(__name__)


def get_now() -> datetime.datetime:
    """
    Get the current time in UTC+8
    """
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def timer(func: "Callable[..., Any]") -> "Callable[..., Any]":
    """
    A decorator that prints the runtime of the decorated function
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        LOGGER_.debug("%s took %.6f seconds to run", func.__name__, time.time() - start)
        return result

    return wrapper
