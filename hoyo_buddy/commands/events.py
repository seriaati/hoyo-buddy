from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import get_locale
from hoyo_buddy.ui.hoyo.events import EventsView

if TYPE_CHECKING:
    from ..enums import Game
    from ..types import Interaction


class EventsCommand:
    def __init__(self, game: Game) -> None:
        self._game = game

    async def run(self, i: Interaction) -> None:
        locale = await get_locale(i)
        view = EventsView(self._game, author=i.user, locale=locale, translator=i.client.translator)
        await view.start(i)
