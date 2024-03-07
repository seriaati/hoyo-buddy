import base64
import datetime
import logging
import math
import re
import time
from typing import TYPE_CHECKING, Any, TypeVar

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

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


async def test_url_validity(url: str, session: aiohttp.ClientSession) -> bool:
    """
    Test if a URL is valid by sending a HEAD request
    """
    try:
        async with session.head(url) as resp:
            return resp.status == 200
    except aiohttp.ClientError:
        return False


def is_image_url(url: str) -> bool:
    """
    Test if a URL is an image URL
    """
    return url.endswith(IMAGE_EXTENSIONS)


def is_valid_hex_color(color: str) -> bool:
    """
    Test if a string is a valid hex color
    """
    return bool(re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color))


def round_down(number: float, decimals: int) -> float:
    factor = 10.0**decimals
    result = math.floor(number * factor) / factor
    if decimals == 0:
        return int(result)
    return result


async def upload_image(
    session: aiohttp.ClientSession, *, image_url: str | None = None, image: bytes | None = None
) -> str:
    api = "https://freeimage.host/api/1/upload"
    data = {
        "key": "6d207e02198a847aa98d0a2a901485a5",
        "source": image_url,
        "format": "json",
    }

    if image is not None:
        # Encode image into base64 string
        image_base64 = base64.b64encode(image).decode("utf-8")
        data["source"] = image_base64

    async with session.post(api, data=data) as resp:
        resp.raise_for_status()

        data = await resp.json()
        return data["image"]["url"]


def format_timedelta(td: datetime.timedelta) -> str:
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"
