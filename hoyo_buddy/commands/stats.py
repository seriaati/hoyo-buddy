from __future__ import annotations

from typing import TYPE_CHECKING

from ..db.models import get_dyk, get_locale
from ..ui.hoyo.stats import StatsView

if TYPE_CHECKING:
    from ..types import Interaction, User


class StatsCommand:
    def __init__(self, user: User) -> None:
        self._user = user

    async def run(self, i: Interaction) -> None:
        await i.response.defer()

        user = self._user or i.user
        account = await i.client.get_account(user.id)
        client = account.client
        locale = await get_locale(i)
        client.set_lang(locale)
        record_cards = await client.get_record_cards()

        view = StatsView(record_cards, author=i.user, locale=locale, translator=i.client.translator)
        await i.followup.send(embed=view.get_card_embed(record_cards[0]), view=view, content=await get_dyk(i))
        view.message = await i.original_response()
