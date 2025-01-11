from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import get_locale
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.utils import ephemeral

from ..ui.hoyo.stats import StatsView

if TYPE_CHECKING:
    from ..types import Interaction, User


class StatsCommand:
    def __init__(self, user: User) -> None:
        self._user = user

    async def run(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        locale = await get_locale(i)

        user = self._user or i.user
        games_available = (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI)
        accounts = await i.client.get_accounts(user.id, games=games_available)
        account = await i.client.get_account(user.id, games=games_available)
        if not accounts:
            raise NoAccountFoundError(games_available)

        view = StatsView(accounts, account.id, author=i.user, locale=locale)
        await view.start(i)
