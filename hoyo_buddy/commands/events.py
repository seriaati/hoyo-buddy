from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db import HoyoAccount, Settings
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.clients.hakushin import ZZZItemCategory
from hoyo_buddy.models.zzz_event import ZZZEventCalendar
from hoyo_buddy.ui.hoyo.event_calendar import EventCalendarView
from hoyo_buddy.ui.hoyo.events import EventsView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ..types import Interaction, User


class EventsCommand:
    @staticmethod
    def get_weapon_name(i: Interaction, weapon_id: int, locale: Locale) -> str | None:
        try:
            choices = i.client.search_autofill[Game.ZZZ][ZZZItemCategory.W_ENGINES][locale]
        except KeyError:
            return None
        for choice in choices:
            if choice.value == str(weapon_id):
                return choice.name
        return None

    @staticmethod
    async def run(i: Interaction, *, user: User, account: HoyoAccount | None) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)

        user = user or i.user
        account = account or await i.client.get_account(
            user.id, games=COMMANDS["events"].games, platform=COMMANDS["events"].platform
        )

        client = account.client
        client.set_lang(locale)

        if account.game is Game.GENSHIN:
            calendar = await client.get_genshin_event_calendar(account.uid)
        elif account.game is Game.STARRAIL:
            calendar = await client.get_starrail_event_calendar()
        elif account.game is Game.ZZZ:
            events = await client.get_zzz_event_calendar(account.uid)
            gacha_calendar = await client.get_zzz_gacha_calendar(account.uid)

            for banner in gacha_calendar.weapons:
                for weapon in banner.weapons:
                    name = EventsCommand.get_weapon_name(i, weapon.id, locale) or "???"
                    weapon.__dict__["name"] = name

            calendar = ZZZEventCalendar(
                events=events, characters=gacha_calendar.characters, weapons=gacha_calendar.weapons
            )
        else:
            calendar = None

        if calendar is not None:
            view = EventCalendarView(
                calendar, account, author=i.user, locale=locale, dark_mode=settings.dark_mode
            )
        else:
            view = EventsView(account, author=i.user, locale=locale)
        await view.start(i)
