from __future__ import annotations

from typing import TYPE_CHECKING

import discord.utils as dutils
from discord import Member, User
from seria.utils import shorten

from hoyo_buddy.emojis import PROJECT_AMBER
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ambr.models import BookDetail, BookVolume

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction


class BookVolumeUI(View):
    def __init__(
        self, book: BookDetail, ambr_api_lang: str, *, author: User | Member, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)

        self.book = book
        self.selected_volume = book.volumes[0]
        self.ambr_api_lang = ambr_api_lang

    async def _fetch_volume_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale) as api:
            readable = await api.fetch_readable(f"Book{self.selected_volume.story_id}")
            return api.get_volume_embed(self.book, self.selected_volume, readable)

    def _setup_items(self) -> None:
        self.clear_items()
        self.add_item(VolumeSelector(self.book.volumes, self.selected_volume))
        self.add_item(
            Button(
                label="ambr.top",
                url=f"https://ambr.top/{self.ambr_api_lang}/archive/book/{self.book.id}",
                emoji=PROJECT_AMBER,
            )
        )

    async def start(self, i: Interaction) -> None:
        embed = await self._fetch_volume_embed()
        self._setup_items()
        self.message = await i.edit_original_response(embed=embed, view=self)


class VolumeSelector(Select["BookVolumeUI"]):
    def __init__(self, volumes: list[BookVolume], selected_volume: BookVolume) -> None:
        super().__init__(
            placeholder=LocaleStr(key="volume_selector_placeholder"),
            options=[
                SelectOption(
                    label=shorten(volume.name, 100),
                    value=str(volume.id),
                    default=volume.id == selected_volume.id,
                )
                for volume in volumes
            ],
        )
        self.volumes = volumes

    async def callback(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        volume = dutils.get(self.volumes, id=int(self.values[0]))
        if volume is None:
            return
        self.view.selected_volume = volume
        embed = await self.view._fetch_volume_embed()

        self.view._setup_items()
        await i.edit_original_response(embed=embed, view=self.view)
