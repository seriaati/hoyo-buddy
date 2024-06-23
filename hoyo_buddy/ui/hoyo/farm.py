from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from ...bot.translator import EnumStr, LocaleStr, Translator, WeekdayStr
from ...constants import UID_TZ_OFFSET, WEEKDAYS
from ...draw.main_funcs import draw_farm_card
from ...embeds import DefaultEmbed
from ...emojis import BELL_OUTLINE, GENSHIN_CITY_EMOJIS
from ...enums import GenshinCity
from ...hoyo.farm_data import FarmDataFetcher
from ...models import DrawInput
from ...utils import get_now
from ..components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from ...types import Interaction


class FarmView(View):
    def __init__(
        self,
        uid: int | None,
        dark_mode: bool,
        *,
        author: User | Member | None,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._uid = uid
        self._dark_mode = dark_mode

        self._weekday: int = 0
        self._determine_weekday()
        self._city: GenshinCity = GenshinCity.MONDSTADT

    def _determine_weekday(self) -> None:
        for uid_start, offset in UID_TZ_OFFSET.items():
            if str(self._uid).startswith(uid_start):
                self._weekday = (get_now() + timedelta(hours=offset)).weekday()
                break
        else:
            self._weekday = get_now().weekday()

    async def start(self, i: Interaction) -> None:
        await i.response.defer()

        self.clear_items()
        self.add_item(WeekdaySelect(self._weekday))
        for city in GenshinCity:
            self.add_item(CityButton(city, self._city))
        self.add_item(ReminderButton())

        if self._weekday == 6:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr(key="farm_view.sundays"),
                description=LocaleStr(key="farm_view.happy_farming"),
            )
            await i.edit_original_response(embed=embed, view=self, attachments=[])
            self.message = await i.original_response()
            return

        draw_input = DrawInput(
            dark_mode=self._dark_mode,
            locale=self.locale,
            session=i.client.session,
            filename="farm.webp",
            executor=i.client.executor,
            loop=i.client.loop,
        )
        file_ = await draw_farm_card(
            draw_input,
            await FarmDataFetcher.fetch(self._weekday, self.translator, city=self._city),
            self.translator,
        )

        await i.edit_original_response(attachments=[file_], view=self, embed=None)
        self.message = await i.original_response()


class WeekdaySelect(Select[FarmView]):
    def __init__(self, current: int) -> None:
        super().__init__(
            placeholder=LocaleStr(key="farm_view.weekday_select.placeholder"),
            options=[
                SelectOption(
                    label=WeekdayStr(weekday), value=str(weekday), default=weekday == current
                )
                for weekday in WEEKDAYS
            ],
            row=0,
        )

    async def callback(self, i: Interaction) -> None:
        self.view._weekday = int(self.values[0])
        self.update_options_defaults()
        await self.view.start(i)


class ReminderButton(Button[FarmView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="farm_view.set_reminder"),
            style=ButtonStyle.green,
            emoji=BELL_OUTLINE,
            row=2,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(key="farm_view.set_reminder.embed.description"),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class CityButton(Button[FarmView]):
    def __init__(self, city: GenshinCity, current: GenshinCity) -> None:
        super().__init__(
            label=EnumStr(city),
            style=ButtonStyle.blurple if city == current else ButtonStyle.secondary,
            emoji=GENSHIN_CITY_EMOJIS[city],
            custom_id=f"city_{city.value.lower()}_btn",
            row=1,
        )
        self._city = city

    async def callback(self, i: Interaction) -> None:
        self.view._city = self._city
        await self.view.start(i)
