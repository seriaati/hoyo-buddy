from __future__ import annotations

import asyncio
import base64
import datetime
import hashlib
import math
import pathlib
import re
import time
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

import aiohttp
import discord
import orjson
import sentry_sdk
import toml
from discord.ext import commands
from loguru import logger

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    HB_BIRTHDAY,
    IMAGE_EXTENSIONS,
    SLEEP_TIMES,
    STATIC_FOLDER,
    TRAVELER_IDS,
    UTC_8,
)
from hoyo_buddy.emojis import MIMO_POINT_EMOJIS
from hoyo_buddy.enums import Game

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    import genshin

    from hoyo_buddy.types import Interaction, SleepTime

__all__ = (
    "add_to_hoyo_codes",
    "blur_uid",
    "capitalize_first_word",
    "capture_exception",
    "contains_masked_link",
    "convert_chara_id_to_ambr_format",
    "convert_code_to_redeem_url",
    "convert_to_title_case",
    "dict_cookie_to_str",
    "ephemeral",
    "error_handler",
    "fetch_json",
    "format_float",
    "format_time",
    "format_timedelta",
    "get_discord_protocol_url",
    "get_discord_url",
    "get_discord_user_link",
    "get_discord_user_md_link",
    "get_floor_difficulty",
    "get_mimo_task_str",
    "get_mimo_task_url",
    "get_now",
    "get_pixiv_proxy_img",
    "get_project_version",
    "get_static_img_path",
    "human_format_number",
    "is_hb_birthday",
    "is_image_url",
    "is_valid_hex_color",
    "measure_time",
    "remove_html_tags",
    "seconds_to_time",
    "should_ignore_error",
    "sleep",
    "test_url_validity",
    "upload_image",
    "wrap_task_factory",
)


def get_now(tz: datetime.timezone | None = None) -> datetime.datetime:
    """Get the current time in UTC+8 or the specified timezone."""
    return datetime.datetime.now(tz or UTC_8)


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
    from hoyo_buddy.exceptions import ImageFileTooLargeError  # noqa: PLC0415

    if CONFIG.img_upload_api_key is None:
        msg = "Image upload API key is not set"
        raise ValueError(msg)

    api = "https://img.seria.moe/upload"
    data = {"key": CONFIG.img_upload_api_key}

    if image is not None:
        # Encode image into base64 string
        image_base64 = base64.b64encode(image).decode("utf-8")
        data["source"] = image_base64
    if image_url is not None:
        data["source"] = image_url

    async with session.post(api, json=data) as resp:
        if resp.status == 413:  # Payload too large
            raise ImageFileTooLargeError

        resp.raise_for_status()

        data = await resp.json()
        filename = data["filename"]
        return f"https://img.seria.moe/{filename}"


def should_ignore_error(e: Exception) -> bool:
    errors_to_ignore = (
        aiohttp.ClientConnectorError,
        aiohttp.ServerDisconnectedError,
        discord.DiscordServerError,
        discord.app_commands.CheckFailure,
        StopAsyncIteration,
        commands.CommandNotFound,
        commands.TooManyArguments,
        commands.CheckFailure,
        commands.MissingRequiredArgument,
        commands.BadLiteralArgument,
    )
    if isinstance(e, errors_to_ignore):
        return True

    # 10062: Unknown interaction
    # 10008: Unknown message
    # 40060: Interaction has already been acknowledged
    if isinstance(e, discord.HTTPException) and e.code in {10062, 10008, 40060}:  # noqa: SIM103
        return True

    return False


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


def blur_uid(uid: int, *, arterisk: str = "*") -> str:
    """Blur a UID by replacing the middle 5 digits with asterisks."""
    uid_ = str(uid)
    middle_index = len(uid_) // 2
    return uid_[: middle_index - 1] + arterisk * 3 + uid_[middle_index + 2 :]


def get_discord_user_link(user_id: int) -> str:
    """Get the link to a Discord user's profile."""
    return f"https://discord.com/users/{user_id}"


def get_discord_user_md_link(user: discord.User | discord.Member) -> str:
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
    s = s[0].upper() + s[1:]
    # Capitalize the first word after a colon
    return re.sub(r"(:\s*)([a-z])", lambda match: match.group(1) + match.group(2).upper(), s)


def capitalize_first_word(s: str) -> str:
    """Capitalize the first word of the input string, decapitalize the rest of the words,
    and leave the first word after a colon unchanged."""
    words = s.split()
    if not words:
        return s

    formatted_words: list[str] = []
    capitalize_next = True  # Capitalize the first word initially
    ends_with_colon = words[0].endswith(":")

    for word in words:
        if capitalize_next:
            formatted_words.append(word.capitalize())
            capitalize_next = False
        elif ends_with_colon:
            formatted_words.append(word)
        else:
            formatted_words.append(word.lower())

        ends_with_colon = word.endswith(":")

    return " ".join(formatted_words)


async def get_pixiv_proxy_img(session: aiohttp.ClientSession, url: str) -> str:
    """Get the proxy image URL for a Pixiv artwork."""
    # Example: https://i.pximg.net/img-master/img/2024/05/18/19/37/42/118837522_p0_master1200.jpg
    filename = url.rsplit("/", maxsplit=1)[-1]
    artwork_id = filename.split("_")[0]

    api = f"https://phixiv.net/api/info?id={artwork_id}"
    async with session.get(api) as resp:
        resp.raise_for_status()
        data = await resp.json()
        proxy_img_urls: list[str] = data["image_proxy_urls"]

    for img_url in proxy_img_urls:
        proxy_filename = img_url.rsplit("/", maxsplit=1)[-1]
        if proxy_filename == filename:
            return img_url

    return proxy_img_urls[0]


def get_floor_difficulty(floor_name: str, season_name: str) -> str:
    """Get the difficulty of a floor in a Star Rail challenge."""
    return floor_name.replace(season_name, "").replace(":", "").replace("•", "").strip()


def get_static_img_path(image_url: str) -> pathlib.Path:
    if not image_url:
        msg = "Invalid image URL"
        raise ValueError(msg)

    parsed_url = urlparse(image_url)
    path = unquote(parsed_url.path)
    path_without_leading_slash = path.lstrip("/")
    full_path = pathlib.Path(parsed_url.netloc) / pathlib.Path(path_without_leading_slash)

    if parsed_url.query:
        query_hash = hashlib.sha256(parsed_url.query.encode()).hexdigest()[:8]
        new_name = f"{full_path.stem}_{query_hash}{full_path.suffix}"
        full_path = full_path.with_name(new_name)

    return STATIC_FOLDER / full_path


def remove_html_tags(content: str) -> str:
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

    async def coro_wrapper(coro: asyncio._CoroutineLike[Any], coro_name: str | None = None) -> Any:
        try:
            return await coro
        except Exception as e:
            if not should_ignore_error(e):
                name = coro_name or getattr(coro, "__name__", str(coro))
                if CONFIG.sentry:
                    logger.warning(f"Error in task {name!r}: {e}, capturing exception")
                    sentry_sdk.capture_exception(e)
                else:
                    logger.exception(f"Error in task {name!r}: {e}")

            # Still raise the exception, so errors like `StopAsyncIteration` can work properly
            raise

    def new_factory(
        loop: asyncio.AbstractEventLoop, coro: asyncio._CoroutineLike[Any], **kwargs: Any
    ) -> asyncio.Task[Any] | asyncio.Future[Any]:
        wrapped_coro = coro_wrapper(coro, coro_name=kwargs.get("name"))

        if original_factory is not None:
            t = original_factory(loop, wrapped_coro, **kwargs)
        else:
            t = asyncio.Task(wrapped_coro, loop=loop, **kwargs)

        _tasks_set.add(t)
        t.add_done_callback(_tasks_set.discard)
        return t

    loop.set_task_factory(new_factory)


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


def format_time(seconds: int, *, short: bool = False) -> str:
    """Format seconds into a human-readable string.

    Args:
        seconds: The number of seconds to format.
        short: If True, format as MMm SSs. Otherwise, format as HHh MMm SSs.
               If short is False and hours are 0, it will be omitted.

    Returns:
        The formatted time string.
    """
    if short:
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}m {seconds:02d}s"

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

    return f"{minutes:02d}m {seconds:02d}s"


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
    *, channel_id: int, guild_id: int | None, message_id: int | None = None
) -> str:
    """Generate a Discord app protocol URL."""
    protocol = (
        f"discord://-/channels/@me/{channel_id}"
        if guild_id is None
        else f"discord://-/channels/{guild_id}/{channel_id}"
    )
    if message_id is not None:
        protocol += f"/{message_id}"

    return protocol


def get_discord_url(*, channel_id: int, guild_id: int | None, message_id: int | None = None) -> str:
    """Generate a Discord URL for a given channel and guild."""
    url = (
        f"https://discord.com/channels/@me/{channel_id}"
        if guild_id is None
        else f"https://discord.com/channels/{guild_id}/{channel_id}"
    )
    if message_id is not None:
        url += f"/{message_id}"

    return url


def dict_cookie_to_str(cookie_dict: dict[str, str]) -> str:
    """Convert a dictionary cookie to a string.

    Args:
        cookie_dict: The cookie dictionary.

    Returns:
        The cookie string.
    """

    return "; ".join([f"{key}={value}" for key, value in cookie_dict.items()])


def get_project_version() -> str:
    data = toml.load("pyproject.toml")
    return f"v{data['project']['version']}"


async def fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return orjson.loads(await resp.read())


def ephemeral(i: Interaction) -> bool:
    return not i.app_permissions.embed_links


@contextmanager
def measure_time(name: str) -> Generator[Any, None, None]:
    start_time = time.perf_counter()
    try:
        yield
    finally:
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        print(f"Execution time of {name}: {execution_time:.8f} seconds")  # noqa: T201


@contextmanager
def error_handler() -> Generator[Any, None, None]:
    try:
        yield
    except Exception:
        logger.exception("Error occurred")


def convert_code_to_redeem_url(code: str, *, game: Game) -> str:
    if game is Game.GENSHIN:
        return f"[{code}](<https://genshin.hoyoverse.com/en/gift?code={code}>)"
    if game is Game.STARRAIL:
        return f"[{code}](<https://hsr.hoyoverse.com/gift?code={code}>)"
    if game is Game.ZZZ:
        return f"[{code}](<https://zenless.hoyoverse.com/redemption?code={code}>)"

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)


def get_mimo_task_url(task: genshin.models.MimoTask) -> str | None:
    if not task.jump_url:
        return None

    url_data: dict[str, Any] = orjson.loads(task.jump_url)
    host, type_, args = url_data.get("host"), url_data.get("type"), url_data.get("args")
    if host != "hoyolab" or args is None:
        return None

    if type_ == "article":
        post_id = args.get("post_id")
        if post_id is None:
            return None
        return f"https://www.hoyolab.com/article/{post_id}"

    if type_ == "topicDetail":
        topic_id = args.get("topic_id")
        if topic_id is None:
            return None
        return f"https://www.hoyolab.com/topicDetail/{topic_id}"

    if type_ == "circles":
        game_id = args.get("game_id")
        if game_id is None:
            return None
        return f"https://www.hoyolab.com/circles/{game_id}"

    if type_ == "h5":
        url = args.get("url")
        if url is None:
            return None
        return url

    return None


def get_mimo_task_str(task: genshin.models.MimoTask, game: Game) -> str:
    point_emoji = MIMO_POINT_EMOJIS[game]
    task_url = get_mimo_task_url(task)
    task_name = remove_html_tags(task.name)
    task_str = f"[{task_name}]({task_url})" if task_url else task_name
    task_str += f" - {task.point} {point_emoji}"
    if task.total_progress > 1:
        task_str += f" ({task.progress}/{task.total_progress})"
    return task_str


def contains_masked_link(text: str) -> bool:
    pattern = re.compile(r"\[.*?\]\(<?https?://.*?>?\)")
    return bool(pattern.search(text))


async def add_to_hoyo_codes(
    session: aiohttp.ClientSession, *, code: str, game: genshin.Game
) -> None:
    api_key = CONFIG.hoyo_codes_api_key
    if api_key is None:
        logger.warning("Hoyo Codes API key is not set, skipping code addition.")
        return

    url = "https://hoyo-codes.seria.moe/codes"
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {"code": code, "game": game.value}
    async with session.post(url, json=data, headers=headers) as resp:
        if resp.status == 400:
            # Code already exists
            return
        resp.raise_for_status()


async def sleep(name: SleepTime) -> None:
    try:
        time = SLEEP_TIMES[name]
    except KeyError:
        logger.error(f"Invalid sleep time name: {name!r}")
        time = 0.0
    await asyncio.sleep(time)


def is_hb_birthday() -> bool:
    now = get_now()
    return (
        HB_BIRTHDAY.replace(year=now.year)
        <= now.date()
        <= HB_BIRTHDAY.replace(year=now.year) + datetime.timedelta(days=7)
    )


def capture_exception(e: Exception) -> None:
    if should_ignore_error(e):
        return

    if not CONFIG.sentry:
        logger.exception(e)
    else:
        logger.warning(f"Error: {e}, capturing exception")
        sentry_sdk.capture_exception(e)


def handle_autocomplete_errors(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> list[discord.app_commands.Choice[str]]:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            capture_exception(e)
            return []

    return wrapper
