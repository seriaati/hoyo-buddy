from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import HoyoAccount, Settings
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.hoyo.event_calendar import EventCalendarView
from hoyo_buddy.ui.hoyo.events import EventsView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ..types import Interaction, User


class EventsCommand:
    @staticmethod
    async def run(i: Interaction, *, user: User, account: HoyoAccount | None) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)

        user = user or i.user
        account = account or await i.client.get_account(
            user.id, games=(Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
        )

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
                calendar, account, author=i.user, locale=locale, dark_mode=settings.dark_mode
            )
        else:
            view = EventsView(account, author=i.user, locale=locale)
        await view.start(i)
