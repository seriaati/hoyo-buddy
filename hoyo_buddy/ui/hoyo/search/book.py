from typing import TYPE_CHECKING

import discord.utils as dutils
from discord import Locale, Member, User

from ....bot.emojis import PROJECT_AMBER
from ....bot.translator import LocaleStr
from ....hoyo.genshin.ambr import AmbrAPIClient
from ....utils import shorten
from ...ui import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from ambr.models import BookDetail, BookVolume

    from ....bot.bot import INTERACTION
    from ....bot.translator import Translator
    from ....embeds import DefaultEmbed


class BookVolumeUI(View):
    def __init__(
        self,
        book: "BookDetail",
        ambr_api_lang: str,
        *,
        author: User | Member,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.book = book
        self.volume = book.volumes[0]

        self.clear_items()
        self.add_item(VolumeSelector(self.book.volumes))
        self.add_item(
            Button(
                label="ambr.top",
                url=f"https://ambr.top/{ambr_api_lang}/archive/book/{self.book.id}",
                emoji=PROJECT_AMBER,
            )
        )

    async def fetch_volume_embed(self) -> "DefaultEmbed":
        async with AmbrAPIClient(self.locale, self.translator) as api:
            readable = await api.fetch_readable(f"Book{self.volume.story_id}")
            embed = api.get_volume_embed(self.book, self.volume, readable)
            return embed

    async def update(self, i: "INTERACTION") -> None:
        embed = await self.fetch_volume_embed()
        await i.edit_original_response(embed=embed, view=self)


class VolumeSelector(Select["BookVolumeUI"]):
    def __init__(self, volumes: list["BookVolume"]) -> None:
        super().__init__(
            placeholder=LocaleStr("Select a volume", key="volume_selector_placeholder"),
            options=[
                SelectOption(label=shorten(volume.name, 100), value=str(volume.id))
                for volume in volumes
            ],
        )
        self.volumes = volumes

    async def callback(self, i: "INTERACTION") -> None:
        await i.response.defer()

        volume = dutils.get(self.volumes, id=int(self.values[0]))
        if volume is None:
            msg = "Invalid volume ID"
            raise AssertionError(msg)

        self.view.volume = volume
        await self.view.update(i)
