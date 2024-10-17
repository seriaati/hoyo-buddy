from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aiofiles
from fake_useragent import UserAgent

from ..exceptions import DownloadImageFailedError
from ..utils import get_static_img_path

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Sequence

    import aiohttp

__all__ = ("download_images",)

ua = UserAgent()
ZZZ_GAME_RECORD = "https://act-webstatic.hoyoverse.com/game_record/zzz/"


async def download_image_task(
    image_url: str, file_path: pathlib.Path, session: aiohttp.ClientSession, *, ignore_error: bool = False
) -> None:
    async with session.get(image_url, headers={"User-Agent": ua.random}) as resp:
        if resp.status != 200:
            if ZZZ_GAME_RECORD in image_url:
                image_url = image_url.replace(ZZZ_GAME_RECORD, ZZZ_GAME_RECORD.replace("zzz", "nap"))
                return await download_image_task(image_url, file_path, session)
            if ignore_error:
                return None
            raise DownloadImageFailedError(image_url, resp.status)

        image = await resp.read()

    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(image)
    return None


async def download_images(
    image_urls: Sequence[str], folder: str, session: aiohttp.ClientSession, *, ignore_error: bool = False
) -> None:
    async with asyncio.TaskGroup() as tg:
        for image_url in list(set(image_urls)):
            file_path = get_static_img_path(image_url, folder)
            if file_path.exists():
                continue
            tg.create_task(download_image_task(image_url, file_path, session, ignore_error=ignore_error))
