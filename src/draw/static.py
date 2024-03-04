import asyncio
import os
from typing import TYPE_CHECKING

import aiofiles

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiohttp

__all__ = ("download_and_save_static_images", "STATIC_FOLDER")

STATIC_FOLDER = "./.static"


async def download_static_image(image_url: str, session: "aiohttp.ClientSession") -> bytes:
    async with session.get(image_url) as resp:
        if resp.status != 200:
            msg = f"Failed to download image: {image_url}"
            raise ValueError(msg)
        image = await resp.read()
        return image


async def save_static_image(folder: str, filename: str, image: bytes) -> None:
    if not os.path.exists(STATIC_FOLDER):
        os.makedirs(STATIC_FOLDER)
    if not os.path.exists(f"{STATIC_FOLDER}/{folder}"):
        os.makedirs(f"{STATIC_FOLDER}/{folder}")

    async with aiofiles.open(f"{STATIC_FOLDER}/{folder}/{filename}", "wb") as f:
        await f.write(image)


async def download_and_save_static_image_task(
    image_url: str, folder: str, filename: str, session: "aiohttp.ClientSession"
) -> None:
    image = await download_static_image(image_url, session)
    await save_static_image(folder, filename, image)


async def download_and_save_static_images(
    image_urls: "Sequence[str]", folder: str, session: "aiohttp.ClientSession"
) -> None:
    tasks: "list[asyncio.Task]" = []
    for image_url in image_urls:
        filename = image_url.split("/")[-1]
        if not os.path.exists(f"{STATIC_FOLDER}/{folder}/{filename}"):
            tasks.append(
                asyncio.create_task(
                    download_and_save_static_image_task(image_url, folder, filename, session)
                )
            )

    await asyncio.gather(*tasks)
