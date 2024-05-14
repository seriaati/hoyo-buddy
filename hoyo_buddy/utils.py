import base64
import datetime
import logging
import re
from typing import TYPE_CHECKING, TypeVar

import aiohttp

if TYPE_CHECKING:
    from discord import Member, User

T = TypeVar("T")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

LOGGER_ = logging.getLogger(__name__)


def get_now() -> datetime.datetime:
    """Get the current time in UTC+8."""
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


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


def get_discord_user_md_link(user: "User | Member") -> str:
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
