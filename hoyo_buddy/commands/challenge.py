from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.constants import CHALLENGE_TYPE_GAMES

from ..db.models import HoyoAccount, Settings
from ..ui.hoyo.challenge import ChallengeView

if TYPE_CHECKING:
    from ..enums import ChallengeType
    from ..types import Interaction, User


class ChallengeCommand:
    def __init__(self, interaction: Interaction, user: User, account: HoyoAccount | None) -> None:
        self._user = user
        self._bot = interaction.client
        self._interaction = interaction
        self._user_id = interaction.user.id
        self._account = account

    async def run(self, challenge_type: ChallengeType) -> None:
        i = self._interaction

        user = self._user or i.user
        account = self._account or await self._bot.get_account(
            user.id, (CHALLENGE_TYPE_GAMES[challenge_type],)
        )
        settings = await Settings.get(user_id=self._user_id)
        locale = settings.locale or i.locale

        view = ChallengeView(
            account, settings.dark_mode, challenge_type, author=i.user, locale=locale
        )
        await view.start(i)
