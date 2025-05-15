from __future__ import annotations

from typing import TYPE_CHECKING

import aiofiles

from ..exceptions import DownloadImageFailedError
from ..utils import TaskGroup, get_static_img_path

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Sequence

    import aiohttp

__all__ = ("download_images",)

ZZZ_GAME_RECORD = "https://act-webstatic.hoyoverse.com/game_record/zzz/"
NAP_GAME_RECORD = "https://act-webstatic.hoyoverse.com/game_record/nap/"
ZZZ_V2_GAME_RECORD = "https://act-webstatic.hoyoverse.com/game_record/zzzv2/"


async def download_image_task(
    image_url: str,
    file_path: pathlib.Path,
    session: aiohttp.ClientSession,
    *,
    ignore_error: bool = False,
) -> None:
    async with session.get(image_url) as resp:
        if resp.status != 200:
            if ZZZ_GAME_RECORD in image_url:
                image_url = image_url.replace(ZZZ_GAME_RECORD, ZZZ_V2_GAME_RECORD)
                return await download_image_task(image_url, file_path, session)
            if NAP_GAME_RECORD in image_url:
                image_url = image_url.replace(NAP_GAME_RECORD, ZZZ_V2_GAME_RECORD)
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
    image_urls: Sequence[str],
    folder: str,
    session: aiohttp.ClientSession,
    *,
    ignore_error: bool = False,
) -> None:
    async with TaskGroup() as tg:
        for image_url in set(image_urls):
            if not image_url:
                continue

            file_path = get_static_img_path(image_url, folder)
            if file_path.exists():
                continue
            tg.create_task(
                download_image_task(image_url, file_path, session, ignore_error=ignore_error)
            )
