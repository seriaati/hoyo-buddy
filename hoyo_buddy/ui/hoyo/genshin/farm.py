from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle

from hoyo_buddy.constants import UID_TZ_OFFSET, WEEKDAYS
from hoyo_buddy.db import get_dyk
from hoyo_buddy.draw.main_funcs import draw_farm_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import BELL_OUTLINE, GENSHIN_CITY_EMOJIS
from hoyo_buddy.enums import GenshinCity
from hoyo_buddy.hoyo.farm_data import FarmDataFetcher
from hoyo_buddy.l10n import EnumStr, LocaleStr, WeekdayStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral, get_now

if TYPE_CHECKING:
    from discord import Member, User

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction


class FarmView(View):
    def __init__(
        self, uid: int | None, *, dark_mode: bool, author: User | Member | None, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)

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
        await i.response.defer(ephemeral=ephemeral(i))

        self.clear_items()
        self.add_item(WeekdaySelect(self._weekday))
        self.add_item(CitySelect(self._city))
        self.add_item(ReminderButton())

        await i.edit_original_response(view=self, **await self.get_message_kwargs(i))
        self.message = await i.original_response()

    async def get_message_kwargs(self, i: Interaction) -> dict[str, Any]:
        content = await get_dyk(i)

        if self._weekday == 6:
            embed = DefaultEmbed(
                self.locale,
                title=LocaleStr(key="farm_view.sundays"),
                description=LocaleStr(key="farm_view.happy_farming"),
            )
            return {"embed": embed, "attachments": [], "content": content}

        draw_input = DrawInput(
            dark_mode=self._dark_mode,
            locale=self.locale,
            session=i.client.session,
            filename="farm.png",
            executor=i.client.executor,
            loop=i.client.loop,
        )
        file_ = await draw_farm_card(
            draw_input, await FarmDataFetcher.fetch(self._weekday, city=self._city)
        )
        return {"attachments": [file_], "embed": None, "content": content}


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
        await self.set_loading_state(i)
        await self.unset_loading_state(i, **await self.view.get_message_kwargs(i))


class ReminderButton(Button[FarmView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="farm_view.set_reminder"),
            style=ButtonStyle.green,
            emoji=BELL_OUTLINE,
            row=4,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale, description=LocaleStr(key="farm_view.set_reminder.embed.description")
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class CitySelect(Select[FarmView]):
    def __init__(self, current: GenshinCity) -> None:
        super().__init__(
            placeholder=LocaleStr(key="farm_view.city_select.placeholder"),
            options=[
                SelectOption(
                    label=EnumStr(city),
                    value=city.value,
                    emoji=GENSHIN_CITY_EMOJIS[city],
                    default=city == current,
                )
                for city in GenshinCity
            ],
            row=1,
        )

    async def callback(self, i: Interaction) -> None:
        self.view._city = GenshinCity(self.values[0])
        await self.set_loading_state(i)
        await self.unset_loading_state(i, **await self.view.get_message_kwargs(i))
