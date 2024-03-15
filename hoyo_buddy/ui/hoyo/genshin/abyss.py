from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.main_funcs import draw_item_list_card
from hoyo_buddy.hoyo.clients.ambr_client import AmbrAPIClient
from hoyo_buddy.models import DrawInput

from ....utils import get_now
from ...components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from ambr.models import Abyss, AbyssResponse

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.models import ItemWithDescription


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
        self._season_index = 0

        self._abyss_data: "AbyssResponse | None" = None
        self._monster_curve: dict[str, dict[str, dict[str, float]]] | None = None

    def add_items(self) -> None:
        assert self._abyss_data is not None

        self.add_item(AbyssSeasonSelector(self._abyss_data.abyss_items, self._season_index))
        self.add_item(FloorSelect(self._floor_index))
        for chamber_index in range(3):
            self.add_item(ChamberButton(chamber_index))
        for wave_index in range(2):
            self.add_item(WaveButton(wave_index))

    def _update_item_styles(self, item_num: int) -> None:
        # Update chamber button color
        for index in range(3):
            chamber_btn: ChamberButton = self.get_item(f"chamber_{index}_btn")
            chamber_btn.style = (
                ButtonStyle.secondary if index != self._chamber_index else ButtonStyle.primary
            )

        # Disable wave buttons if there is only one wave
        if item_num == 1:
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

    def _determine_season_index(self) -> None:
        assert self._abyss_data is not None
        for index, abyss_item in enumerate(self._abyss_data.abyss_items):
            if abyss_item.open_time <= get_now().replace(tzinfo=None) <= abyss_item.close_time:
                self._season_index = index
                break

    async def _get_embed_and_enemy_items(
        self,
    ) -> tuple["DefaultEmbed", tuple[list["ItemWithDescription"], list["ItemWithDescription"]]]:
        assert self._abyss_data is not None and self._monster_curve is not None

        async with AmbrAPIClient(self.locale, self.translator) as client:
            abyss = self._abyss_data.abyss_items[self._season_index]

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
                enemies=self._abyss_data.enemies,
                floor_enemy_level=floor.override_enemy_level,
                monster_curve=self._monster_curve,
            )

        return embed, items

    async def _update(self, i: "INTERACTION", *, defer: bool = True) -> None:
        if defer:
            await i.response.defer()

        embed, items = await self._get_embed_and_enemy_items()
        self.clear_items()
        self.add_items()

        # Draw card
        file_ = await draw_item_list_card(
            DrawInput(
                dark_mode=self._dark_mode,
                locale=self.locale,
                session=i.client.session,
                filename="enemies.webp",
            ),
            items[self._wave_index],
        )

        # Update item styles
        self._update_item_styles(len(items))

        await i.edit_original_response(embed=embed, attachments=[file_], view=self)
        self.message = await i.original_response()

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        async with AmbrAPIClient(self.locale, self.translator) as client:
            self._abyss_data = await client.fetch_abyss_data()
            self._monster_curve = await client.fetch_monster_curve()

        self._determine_season_index()
        await self._update(i, defer=False)


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
            row=1,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._floor_index = int(self.values[0])
        self.view._chamber_index = 0
        self.view._wave_index = 0
        self.update_options_defaults()
        await self.view._update(i)


class ChamberButton(Button[AbyssView]):
    def __init__(self, chamber_index: int) -> None:
        super().__init__(
            label=LocaleStr(
                "Chamber {value}", key="chamber_button_label", value=str(chamber_index + 1)
            ),
            custom_id=f"chamber_{chamber_index}_btn",
            row=2,
        )

        self._chamber_index = chamber_index

    async def callback(self, i: "INTERACTION") -> None:
        self.view._chamber_index = self._chamber_index
        self.view._wave_index = 0
        await self.view._update(i)


class WaveButton(Button[AbyssView]):
    def __init__(self, wave_index: int) -> None:
        super().__init__(
            label=LocaleStr("Wave {value}", key="wave_button_label", value=str(wave_index + 1)),
            custom_id=f"wave_{wave_index}_btn",
            row=3,
        )

        self._wave_index = wave_index

    async def callback(self, i: "INTERACTION") -> None:
        self.view._wave_index = self._wave_index
        await self.view._update(i)


class AbyssSeasonSelector(Select[AbyssView]):
    def __init__(self, abyss_items: list["Abyss"], current: int) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=f"{item.open_time.strftime('%m/%d/%Y')} ~ {item.close_time.strftime('%m/%d/%Y')}",
                    value=str(index),
                    default=index == current,
                )
                for index, item in enumerate(abyss_items)
            ],
            row=0,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._season_index = int(self.values[0])
        self.view._floor_index = 12
        self.view._chamber_index = 0
        self.view._wave_index = 0
        await self.view._update(i)
