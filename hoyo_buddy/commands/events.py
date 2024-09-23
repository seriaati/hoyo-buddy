from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import HoyoAccount, get_locale
from hoyo_buddy.ui.hoyo.events import EventsView

if TYPE_CHECKING:
    from ..types import Interaction


class EventsCommand:
    @staticmethod
    async def run(i: Interaction, *, account: HoyoAccount) -> None:
        locale = await get_locale(i)
        view = EventsView(account, author=i.user, locale=locale, translator=i.client.translator)
        await view.start(i)
