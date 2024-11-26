from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import HoyoAccount, Settings
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.hoyo.event_calendar import EventCalendarView
from hoyo_buddy.ui.hoyo.events import EventsView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ..types import Interaction


class EventsCommand:
    @staticmethod
    async def run(i: Interaction, *, account: HoyoAccount) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        settings = await Settings.get(user_id=i.user.id)
        locale = settings.locale or i.locale
        client = account.client
        client.set_lang(locale)

        if account.game is Game.GENSHIN:
            calendar = await client.get_genshin_event_calendar(account.uid)
        elif account.game is Game.STARRAIL:
            calendar = await client.get_starrail_event_calendar()
        else:
            calendar = None

        if calendar is not None:
            view = EventCalendarView(
                calendar, author=i.user, locale=locale, dark_mode=settings.dark_mode
            )
        else:
            view = EventsView(account, author=i.user, locale=locale)
        await view.start(i)
