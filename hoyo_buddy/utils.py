from __future__ import annotations

import asyncio
import base64
import datetime
import math
import re
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import aiohttp
from loguru import logger
from seria.utils import clean_url

from .constants import IMAGE_EXTENSIONS, STATIC_FOLDER, TRAVELER_IDS, UTC_8

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Generator

    from discord import Interaction, Member, User


def get_now() -> datetime.datetime:
    """Get the current time in UTC+8."""
    return datetime.datetime.now(UTC_8)


async def test_url_validity(url: str, session: aiohttp.ClientSession) -> bool:
    """Test if a URL is valid by sending a HEAD request."""
    try:
        async with session.head(url) as resp:
            return resp.status == 200
    except aiohttp.ClientError:
        return False


def is_image_url(url: str) -> bool:
    """Test if a URL is an image URL."""
    return url.endswith(IMAGE_EXTENSIONS)


def is_valid_hex_color(color: str) -> bool:
    """Test if a string is a valid hex color."""
    return bool(re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", color))


async def upload_image(
    session: aiohttp.ClientSession, *, image_url: str | None = None, image: bytes | None = None
) -> str:
    api = "https://freeimage.host/api/1/upload"
    data = {"key": "6d207e02198a847aa98d0a2a901485a5", "source": image_url, "format": "json"}

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


def blur_uid(uid: int) -> str:
    """Blur a UID by replacing the middle 5 digits with asterisks."""
    uid_ = str(uid)
    middle_index = len(uid_) // 2
    return uid_[: middle_index - 1] + "***" + uid_[middle_index + 2 :]


def get_discord_user_link(user_id: int) -> str:
    """Get the link to a Discord user's profile."""
    return f"https://discord.com/users/{user_id}"


def get_discord_user_md_link(user: User | Member) -> str:
    """Get the Markdown-formatted link to a Discord user's profile."""
    return f"[@{user}]({get_discord_user_link(user.id)})"


def convert_to_title_case(s: str) -> str:
    """Convert a string to title case.

    Follows the rules of https://apastyle.apa.org/style-grammar-guidelines/capitalization/title-case
    """
    # Capitalize the first letter of each word
    s = s.title()
    # Lowercase words that are three letters or fewer
    s = re.sub(r"\b\w{1,3}\b", lambda m: m.group().lower(), s)
    # Capitalize first word
    s = capitalize_first_word(s)
    # Capitalize the first word after a colon
    return re.sub(r"(?<=:)\s*\w+", lambda m: m.group().capitalize(), s)


def capitalize_first_word(s: str) -> str:
    """Capitalize the first word of a string and leave the rest unchanged."""
    return s[:1].upper() + s[1:]


async def get_pixiv_proxy_img(session: aiohttp.ClientSession, url: str) -> str:
    """Get the proxy image URL for a Pixiv artwork."""
    # Example: https://i.pximg.net/img-master/img/2024/05/18/19/37/42/118837522_p0_master1200.jpg
    filename = url.split("/")[-1]
    artwork_id = filename.split("_")[0]

    api = f"https://phixiv.net/api/info?id={artwork_id}"
    async with session.get(api) as resp:
        resp.raise_for_status()
        data = await resp.json()
        proxy_img_urls = data["image_proxy_urls"]

    for img_url in proxy_img_urls:
        proxy_filename = img_url.split("/")[-1]
        if proxy_filename == filename:
            return img_url

    return proxy_img_urls[0]


def get_floor_difficulty(floor_name: str, season_name: str) -> str:
    """Get the difficulty of a floor in a Star Rail challenge."""
    return floor_name.replace(season_name, "").replace(":", "").replace("•", "").strip()


def ephemeral(i: Interaction) -> bool:
    """Returns true if the interaction needs to be ephemeral."""
    if i.guild is None:
        return False
    return not i.app_permissions.send_messages


@contextmanager
def measure_time(
    description: str = "Execution", *, print_: bool = False
) -> Generator[None, Any, None]:
    start_time = time.time_ns()
    yield
    end_time = time.time_ns()
    msg = f"{description} time: {(end_time - start_time) / 1e6:.6f} ms"
    if print_:
        print(msg)  # noqa: T201
    else:
        logger.debug(msg)


def get_static_img_path(image_url: str, folder: str) -> pathlib.Path:
    extra_folder = image_url.split("/")[-2]
    filename = clean_url(image_url).split("/")[-1]
    return STATIC_FOLDER / folder / extra_folder / filename


def format_ann_content(content: str) -> str:
    content = content.replace("\\n", "\n")
    # replace tags with style attributes
    content = content.replace("</p>", "\n")
    content = content.replace("<strong>", "**")
    content = content.replace("</strong>", "**")

    # remove all HTML tags
    html_regex = re.compile(r"<[^>]*>|&([a-z0-9]+|#\d{1,6}|#x[0-9a-f]{1,6});")
    content = re.sub(html_regex, "", content)

    # remove time tags from mihoyo
    content = content.replace('t class="t_gl"', "")
    content = content.replace('t class="t_lc"', "")
    content = content.replace('contenteditable="false"', "")
    return content.replace("/t", "")


_tasks_set: set[asyncio.Task[Any] | asyncio.Future[Any]] = set()


def wrap_task_factory() -> None:
    loop = asyncio.get_running_loop()
    original_factory = loop.get_task_factory()

    def new_factory(
        loop: asyncio.AbstractEventLoop, coro: asyncio._CoroutineLike[Any], **kwargs: Any
    ) -> asyncio.Task[Any] | asyncio.Future[Any]:
        if original_factory is not None:
            t = original_factory(loop, coro, **kwargs)
        else:
            t = asyncio.Task(coro, loop=loop, **kwargs)
        _tasks_set.add(t)
        t.add_done_callback(_tasks_set.discard)
        return t

    loop.set_task_factory(new_factory)


def set_or_update_dict(d: dict[str, Any], key: str, value: Any) -> None:
    """Set or update a value in a dictionary."""
    if key in d:
        d[key] = value
    else:
        d.update({key: value})


def convert_chara_id_to_ambr_format(character_id: int, element: str) -> str:
    """Convert character ID to the format used by AmbrAPI (traveler ID contains element)."""
    return (
        f"{character_id}-{element.lower()}" if character_id in TRAVELER_IDS else str(character_id)
    )


def human_format_number(number: int, decimal_places: int = 1) -> str:
    """Convert a number to a human-readable format."""
    millnames = ("", "k", "M", "B", "T")
    n = float(number)
    millidx = max(
        0,
        min(
            len(millnames) - 1,
            int(0 if n == 0 else math.floor(0 if n < 0 else math.log10(abs(n)) / 3)),
        ),
    )

    return f"{n / 10 ** (3 * millidx):.{decimal_places}f}{millnames[millidx]}"


def format_float(num: float, *, decimals: int = 2) -> str:
    """
    Formats a float number to the last non-zero decimal place, while rounding numbers
    larger than 0 to 2 decimal places.

    Args:
        num: The number to be formatted.
        deimals: The number of decimal places to round to when the number is larger than 0.

    Returns:
        The formatted number as a string.
    """
    if num == 0:
        return "0"

    if abs(num) > 0:
        return f"{num:.{decimals}f}"

    # Find the last non-zero decimal place
    str_num = str(num)
    decimal_places = len(str_num.split(".")[1]) - 1
    while str_num[-1] == "0":
        decimal_places -= 1
        str_num = str_num[:-1]

    return f"{num:.{decimal_places}f}"
