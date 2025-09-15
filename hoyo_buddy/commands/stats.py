from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db import get_locale
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
        accounts = await i.client.get_accounts(user.id, games=COMMANDS["stats"].games)
        account = await i.client.get_account(
            user.id, games=COMMANDS["stats"].games, platform=COMMANDS["stats"].platform
        )

        view = StatsView(accounts, account.id, author=i.user, locale=locale)
        await view.start(i)
