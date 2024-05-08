from __future__ import annotations

import asyncio
import pathlib
from typing import TYPE_CHECKING

import aiofiles
from seria.utils import clean_url

from ..exceptions import DownloadImageFailedError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiohttp


STATIC_FOLDER = pathlib.Path("./.static")


async def download_img(image_url: str, session: aiohttp.ClientSession) -> bytes:
    async with session.get(image_url) as resp:
        if resp.status != 200:
            raise DownloadImageFailedError(image_url, resp.status)

        image = await resp.read()
        return image


async def save_img(folder: str, filename: str, image: bytes) -> None:
    folder_path = STATIC_FOLDER / folder
    if not folder_path.exists():
        folder_path.mkdir(parents=True)

    async with aiofiles.open(folder_path / filename, "wb") as f:
        await f.write(image)


async def download_and_save_img(
    image_url: str, folder: str, filename: str, session: aiohttp.ClientSession
) -> None:
    image = await download_img(image_url, session)
    await save_img(folder, filename, image)


async def download_and_save_static_images(
    image_urls: Sequence[str], folder: str, session: aiohttp.ClientSession
) -> None:
    image_urls = list(set(image_urls))

    tasks = []
    for image_url in image_urls:
        filename = clean_url(image_url).split("/")[-1]
        file_path = STATIC_FOLDER / folder / filename
        if not file_path.exists():
            tasks.append(download_and_save_img(image_url, folder, filename, session))

    await asyncio.gather(*tasks)
