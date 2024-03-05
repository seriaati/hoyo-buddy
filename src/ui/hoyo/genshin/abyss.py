import asyncio
from typing import TYPE_CHECKING

from discord import ButtonStyle, File, Locale, Member, User

from ....bot.translator import LocaleStr
from ....draw.item_list import draw_item_list
from ....draw.static import download_and_save_static_images
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from bot.translator import Translator

    from src.bot.bot import INTERACTION


class AbyssView(View):
    def __init__(
        self,
        dark_mode: bool,
        *,
        author: User | Member,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._dark_mode = dark_mode
        self._floor_index = 11
        self._chamber_index = 0
        self._wave_index = 0

    def add_items(self) -> None:
        self.add_item(FloorSelect(self._floor_index))
        for chamber_index in range(3):
            self.add_item(ChamberButton(chamber_index))
        for wave_index in range(2):
            self.add_item(WaveButton(wave_index))

    async def update(self, i: "INTERACTION") -> None:
        await i.response.defer()

        # Get embed and enemy items
        async with AmbrAPIClient(self.locale, self.translator) as client:
            abyss_data = await client.fetch_abyss_data()
            monster_curve = await client.fetch_monster_curve()
            abyss = abyss_data.abyss_items[-1]

            floor = (
                abyss.abyssal_moon_spire.floors[self._floor_index - 8]
                if self._floor_index > 7
                else abyss.abyss_corridor.floors[self._floor_index]
            )
            chamber = floor.chambers[self._chamber_index]

            embed = client.get_abyss_chamber_embed_with_floor_info(
                floor, self._floor_index, chamber, self._chamber_index
            )
            embed.set_image(url="attachment://enemies.webp")

            items = client.get_abyss_chamber_enemy_items(
                chamber,
                enemies=abyss_data.enemies,
                floor_enemy_level=floor.override_enemy_level,
                monster_curve=monster_curve,
            )

        # Draw card
        await download_and_save_static_images(
            [item.icon for item in items[0] + items[1]], "draw-list", i.client.session
        )
        buffer = await asyncio.to_thread(draw_item_list, items[self._wave_index], self._dark_mode)
        buffer.seek(0)
        file_ = File(buffer, filename="enemies.webp")

        # Update chamber button color
        for index in range(3):
            chamber_btn: ChamberButton = self.get_item(f"chamber_{index}_btn")
            chamber_btn.style = (
                ButtonStyle.secondary if index != self._chamber_index else ButtonStyle.primary
            )

        # Disable wave buttons if there is only one wave
        if len(items) == 1:
            # Reset wave index
            self._wave_index = 0
            for index in range(2):
                wave_btn: WaveButton = self.get_item(f"wave_{index}_btn")
                wave_btn.disabled = True

        # Update wave button color
        for index in range(2):
            wave_btn: WaveButton = self.get_item(f"wave_{index}_btn")
            wave_btn.style = (
                ButtonStyle.secondary if index != self._wave_index else ButtonStyle.primary
            )

        await i.edit_original_response(embed=embed, attachments=[file_], view=self)


class FloorSelect(Select[AbyssView]):
    def __init__(self, floor_index: int) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(
                        "Floor {value}", key="floor_select_label", value=str(index + 1)
                    ),
                    value=str(index),
                    default=index == floor_index,
                )
                for index in reversed(range(12))
            ],
            row=0,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._floor_index = int(self.values[0])
        self.view._chamber_index = 0
        self.view._wave_index = 0
        self.update_options_defaults()
        await self.view.update(i)


class ChamberButton(Button[AbyssView]):
    def __init__(self, chamber_index: int) -> None:
        super().__init__(
            label=LocaleStr(
                "Chamber {value}", key="chamber_button_label", value=str(chamber_index + 1)
            ),
            custom_id=f"chamber_{chamber_index}_btn",
            row=1,
        )

        self._chamber_index = chamber_index

    async def callback(self, i: "INTERACTION") -> None:
        self.view._chamber_index = self._chamber_index
        self.view._wave_index = 0
        await self.view.update(i)


class WaveButton(Button[AbyssView]):
    def __init__(self, wave_index: int) -> None:
        super().__init__(
            label=LocaleStr("Wave {value}", key="wave_button_label", value=str(wave_index + 1)),
            custom_id=f"wave_{wave_index}_btn",
            row=2,
        )

        self._wave_index = wave_index

    async def callback(self, i: "INTERACTION") -> None:
        self.view._wave_index = self._wave_index
        await self.view.update(i)
