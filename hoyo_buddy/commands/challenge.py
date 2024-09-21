from __future__ import annotations

from typing import TYPE_CHECKING

from ..db.models import HoyoAccount, Settings
from ..enums import Game
from ..ui.hoyo.challenge import ChallengeView

if TYPE_CHECKING:
    from ..types import Interaction, User


class ChallengeCommand:
    def __init__(self, interaction: Interaction, user: User, account: HoyoAccount | None) -> None:
        self._user = user
        self._bot = interaction.client
        self._interaction = interaction
        self._user_id = interaction.user.id
        self._account = account

    async def run(self) -> None:
        i = self._interaction

        user = self._user or i.user
        account = self._account or await self._bot.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.ZZZ)
        )
        settings = await Settings.get(user_id=self._user_id)
        locale = settings.locale or i.locale
        translator = i.client.translator

        view = ChallengeView(
            account, settings.dark_mode, author=i.user, locale=locale, translator=translator
        )
        await view.start(i)
