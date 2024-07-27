from __future__ import annotations

import asyncio
import pathlib
from typing import TYPE_CHECKING

import aiofiles
from fake_useragent import UserAgent

from ..exceptions import DownloadImageFailedError
from ..utils import get_static_img_path

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiohttp

__all__ = ("download_and_save_static_images",)


async def download_img(image_url: str, session: aiohttp.ClientSession) -> bytes:
    async with session.get(image_url, headers={"User-Agent": UserAgent().random}) as resp:
        if resp.status != 200:
            raise DownloadImageFailedError(image_url, resp.status)

        image = await resp.read()
        return image


async def save_img(file_path: pathlib.Path, image: bytes) -> None:
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(image)


async def download_and_save_img(
    image_url: str, file_path: pathlib.Path, session: aiohttp.ClientSession
) -> None:
    image = await download_img(image_url, session)
    await save_img(file_path, image)


async def download_and_save_static_images(
    image_urls: Sequence[str], folder: str, session: aiohttp.ClientSession
) -> None:
    image_urls = list(set(image_urls))

    tasks = []
    for image_url in image_urls:
        file_path = get_static_img_path(image_url, folder)
        if not file_path.exists():
            tasks.append(download_and_save_img(image_url, file_path, session))

    await asyncio.gather(*tasks)
