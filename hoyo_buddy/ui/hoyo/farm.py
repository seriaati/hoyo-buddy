from datetime import timedelta
from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from ...bot.translator import LocaleStr, Translator
from ...constants import UID_TZ_OFFSET, WEEKDAYS
from ...draw.main_funcs import draw_farm_card
from ...embeds import DefaultEmbed
from ...emojis import BELL_OUTLINE
from ...hoyo.farm_data import FarmDataFetcher
from ...models import DrawInput
from ...utils import get_now
from ..components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from ...bot.bot import INTERACTION


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

        self.add_item(WeekdaySelect(self._weekday))

    def _determine_weekday(self) -> None:
        for uid_start, offset in UID_TZ_OFFSET.items():
            if str(self._uid).startswith(uid_start):
                self._weekday = (get_now() + timedelta(hours=offset)).weekday()
                break
        else:
            self._weekday = get_now().weekday()

    async def start(self, i: "INTERACTION") -> None:
        if self._weekday == 6:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Every domain is available on Sundays", key="farm_view.sundays"),
                description=LocaleStr("🌾 Happy farming!", key="farm_view.happy_farming"),
            )
            return await i.response.send_message(embed=embed, view=self)

        await i.response.defer()

        draw_input = DrawInput(
            dark_mode=self._dark_mode,
            locale=self.locale,
            session=i.client.session,
            filename="farm.webp",
        )
        file_ = await draw_farm_card(
            draw_input, await FarmDataFetcher.fetch(self._weekday, self.translator), self.translator
        )

        await i.edit_original_response(attachments=[file_], view=self)
        self.message = await i.original_response()


class WeekdaySelect(Select[FarmView]):
    def __init__(self, current: int) -> None:
        super().__init__(
            placeholder=LocaleStr("Select a weekday", key="farm_view.weekday_select.placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr(label, warn_no_key=False),
                    value=str(value),
                    default=value == current,
                )
                for value, label in WEEKDAYS.items()
            ],
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._weekday = int(self.values[0])
        self.update_options_defaults()
        await self.view.start(i)


class ReminderButton(Button[FarmView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Set reminder", key="farm_view.set_reminder"),
            style=ButtonStyle.blurple,
            emoji=BELL_OUTLINE,
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(
                "To set reminders, use the </farm notify> command",
                key="farm_view.set_reminder.embed.description",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)
