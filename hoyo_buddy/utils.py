from __future__ import annotations

import base64
import datetime
import re
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import aiohttp
from loguru import logger
from seria.utils import clean_url

from .constants import IMAGE_EXTENSIONS, STATIC_FOLDER, UTC_8

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
    s = re.sub(r"(?<=:)\s*\w+", lambda m: m.group().capitalize(), s)
    return s


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
