from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.constants import IMAGE_EXTENSIONS
from hoyo_buddy.exceptions import NotAnImageError
from hoyo_buddy.utils import ephemeral, upload_image

if TYPE_CHECKING:
    import aiohttp
    from discord import Interaction


class UploadCommand:
    @staticmethod
    async def execute(
        i: Interaction, filename: str, url: str, session: aiohttp.ClientSession
    ) -> None:
        if not any(filename.endswith(ext) for ext in IMAGE_EXTENSIONS):
            raise NotAnImageError

        await i.response.defer(ephemeral=ephemeral(i))
        url = await upload_image(session, image_url=url)
        await i.followup.send(f"<{url}>", ephemeral=True)
