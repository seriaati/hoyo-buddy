from __future__ import annotations

import asyncio
import base64
import datetime
import http.cookies
import math
import os
import re
from typing import TYPE_CHECKING, Any, overload

import aiohttp
import ambr
import git
import orjson
import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.loguru import LoggingLevels, LoguruIntegration
from seria.utils import clean_url

from hoyo_buddy.enums import Game

from .constants import IMAGE_EXTENSIONS, STATIC_FOLDER, TRAVELER_IDS, UTC_8

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Sequence

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
    """
    Format a timedelta object into a string in the format HH:MM:SS.

    Args:
        td: A timedelta object representing the duration to format.

    Returns:
        A string representing the formatted duration in the format HH:MM:SS.
    """
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def seconds_to_time(seconds: int) -> str:
    """
    Convert a number of seconds into a time string formatted as HH:MM:SS.

    Args:
        seconds: The number of seconds to convert.

    Returns:
        The formatted time string in HH:MM:SS format.
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours == 0:
        return f"{minutes:02}:{seconds:02}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


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


def get_discord_protocol_url(
    *, channel_id: str, guild_id: str, message_id: str | None = None
) -> str:
    """
    Generate a Discord protocol URL.
    Args:
        channel_id (str): The ID of the Discord channel.
        guild_id (str): The ID of the Discord guild (server). Use "None" for direct messages.
        message_id (str | None, optional): The ID of the specific message. Defaults to None.
    Returns:
        str: The generated Discord protocol URL.
    """
    protocol = (
        f"discord://-/channels/@me/{channel_id}"
        if guild_id == "None"
        else f"discord://-/channels/{guild_id}/{channel_id}"
    )
    if str(message_id) != "None":
        protocol += f"/{message_id}"

    return protocol


def get_discord_url(*, channel_id: str, guild_id: str) -> str:
    """
    Generates a Discord URL for a given channel and guild.

    Args:
        channel_id (str): The ID of the Discord channel.
        guild_id (str): The ID of the Discord guild. If "None", the URL will point to a direct message channel.

    Returns:
        str: The generated Discord URL.
    """
    if guild_id == "None":
        return f"https://discord.com/channels/@me/{channel_id}"
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def str_cookie_to_dict(cookie_string: str) -> dict[str, str]:
    """Convert a string cookie to a dictionary.

    Args:
        cookie_string: The cookie string.

    Returns:
        The cookie dictionary.
    """

    cookies = http.cookies.SimpleCookie()
    cookies.load(cookie_string)
    return {cookie.key: cookie.value for cookie in cookies.values()}


def dict_cookie_to_str(cookie_dict: dict[str, str]) -> str:
    """Convert a dictionary cookie to a string.

    Args:
        cookie_dict: The cookie dictionary.

    Returns:
        The cookie string.
    """

    return "; ".join([f"{key}={value}" for key, value in cookie_dict.items()])


def get_repo_version(repo: git.Repo | None = None) -> str:
    repo = repo or git.Repo()
    tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
    return tags[-1].name


def init_sentry() -> None:
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            AsyncioIntegration(),
            LoguruIntegration(
                level=LoggingLevels.INFO.value, event_level=LoggingLevels.ERROR.value
            ),
        ],
        disabled_integrations=[AsyncPGIntegration(), AioHttpIntegration(), LoggingIntegration()],
        traces_sample_rate=1.0,
        environment=os.environ["ENV"],
        enable_tracing=True,
        release=get_repo_version(),
    )


def _process_query(item_ids_or_names: Sequence[str | int] | int | str) -> str:
    if not isinstance(item_ids_or_names, str | int):
        if len(item_ids_or_names) == 1:
            item_ids_or_names_query = item_ids_or_names[0]
        else:
            item_ids_or_names = [str(item) for item in item_ids_or_names]
            item_ids_or_names_query = ",".join(item_ids_or_names)
            item_ids_or_names_query = f"[{item_ids_or_names_query}]"
    else:
        item_ids_or_names_query = item_ids_or_names

    return str(item_ids_or_names_query)


@overload
async def item_name_to_id(
    session: aiohttp.ClientSession, *, item_names: str, lang: str | None = ...
) -> int: ...
@overload
async def item_name_to_id(
    session: aiohttp.ClientSession, *, item_names: list[str], lang: str | None = ...
) -> list[int]: ...
async def item_name_to_id(
    session: aiohttp.ClientSession, *, item_names: list[str] | str, lang: str | None = None
) -> list[int] | int:
    if lang is None:
        if isinstance(item_names, str):
            async with session.get(f"https://api.uigf.org/identify/genshin/{item_names}") as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["item_id"]

        result: list[int] = []
        for item_name in item_names:
            async with session.get(f"https://api.uigf.org/identify/genshin/{item_name}") as resp:
                resp.raise_for_status()
                data = await resp.json()
                result.append(data["item_id"])

        return result

    item_names_query = _process_query(item_names)

    async with session.post(
        "https://api.uigf.org/translate/",
        json={"type": "normal", "item_name": item_names_query, "game": "genshin", "lang": lang},
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    return data["item_id"]


async def get_item_ids(
    session: aiohttp.ClientSession, *, item_names: list[str], lang: str | None = None
) -> dict[str, int]:
    item_name_tasks: dict[str, asyncio.Task] = {}

    async with asyncio.TaskGroup() as tg:
        for item_name in item_names:
            if item_name in item_name_tasks:
                continue

            item_name_tasks[item_name] = tg.create_task(
                item_name_to_id(session, item_names=item_name, lang=lang)
            )

    return {item_name: task.result() for item_name, task in item_name_tasks.items()}


@overload
async def item_id_to_name(session: aiohttp.ClientSession, *, item_ids: int, lang: str) -> str: ...
@overload
async def item_id_to_name(
    session: aiohttp.ClientSession, *, item_ids: list[int], lang: str
) -> list[str]: ...
async def item_id_to_name(
    session: aiohttp.ClientSession, *, item_ids: list[int] | int, lang: str
) -> list[str] | str:
    item_ids_query = _process_query(item_ids)

    async with session.post(
        "https://api.uigf.org/translate/",
        json={"type": "reverse", "item_id": item_ids_query, "game": "genshin", "lang": lang},
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()

    return data["item_name"]


async def get_gacha_icon(*, game: Game, item_id: int) -> str:
    """Get the icon URL for a gacha item."""
    if game is Game.ZZZ:
        return f"https://stardb.gg/api/static/zzz/{item_id}.png"

    if game is Game.GENSHIN:
        async with ambr.AmbrAPI() as api:
            if len(str(item_id)) == 5:  # weapon
                weapons = await api.fetch_weapons()
                weapon_icon_map: dict[int, str] = {weapon.id: weapon.icon for weapon in weapons}
                return weapon_icon_map[item_id]

            # character
            characters = await api.fetch_characters()
            character_icon_map: dict[int, str] = {
                int(character.id): character.icon
                for character in characters
                if character.id.isdigit()
            }
            return character_icon_map[item_id]

    if game is Game.STARRAIL:
        if len(str(item_id)) == 5:  # light cone
            return f"https://stardb.gg/api/static/StarRailResWebp/icon/light_cone/{item_id}.webp"

        # character
        return f"https://stardb.gg/api/static/StarRailResWebp/icon/character/{item_id}.webp"

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)


async def fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return orjson.loads(await resp.read())


def get_ranking(number: float, number_list: list[float], *, reverse: bool) -> tuple[int, int]:
    sorted_unique_list = sorted(set(number_list), reverse=reverse)

    try:
        # Find the position of the number (add 1 because index starts at 0)
        position = sorted_unique_list.index(number) + 1
    except ValueError:
        # If the number is not in the list, find where it would be inserted
        position = (
            next(
                (i for i, x in enumerate(sorted_unique_list) if x < number), len(sorted_unique_list)
            )
            + 1
        )

    return position, len(sorted_unique_list)


def contains_chinese(text: str) -> bool:
    """Check if a string contains Chinese characters.

    Args:
        text: The string to check.

    Returns:
        True if the string contains Chinese characters, False otherwise.
    """
    chinese_range = r"[\u4e00-\u9fff]"
    return bool(re.search(chinese_range, text))
