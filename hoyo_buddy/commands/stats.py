from __future__ import annotations

from typing import TYPE_CHECKING

from ..db.models import HoyoAccount, get_dyk, get_locale
from ..ui.hoyo.stats import StatsView

if TYPE_CHECKING:
    import genshin

    from ..types import Interaction, User


class StatsCommand:
    def __init__(self, user: User) -> None:
        self._user = user

    async def run(self, i: Interaction) -> None:
        await i.response.defer()
        locale = await get_locale(i)

        user = self._user or i.user
        accounts = await HoyoAccount.filter(user_id=user.id).all()
        uids = {account.uid for account in accounts}
        record_cards: dict[int, genshin.models.RecordCard] = {}

        for account in accounts:
            if account.uid in record_cards:
                continue

            client = account.client
            client.set_lang(locale)
            cards = await client.get_record_cards()

            for card in cards:
                if card.uid not in uids:
                    continue
                record_cards[card.uid] = card

        record_cards_ = list(record_cards.values())
        view = StatsView(record_cards_, author=i.user, locale=locale, translator=i.client.translator)
        await i.followup.send(embed=view.get_card_embed(record_cards_[0]), view=view, content=await get_dyk(i))
        view.message = await i.original_response()
