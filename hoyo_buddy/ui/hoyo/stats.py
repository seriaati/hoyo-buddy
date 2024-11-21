from __future__ import annotations

from typing import TYPE_CHECKING

from ...embeds import DefaultEmbed
from ...emojis import get_game_emoji
from ...l10n import LevelStr, LocaleStr
from ...utils import blur_uid
from ..components import Select, SelectOption, View

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale
    from genshin.models import RecordCard

    from hoyo_buddy.types import User

    from ...types import Interaction


def get_label(card: RecordCard) -> str:
    if not card.nickname:
        return blur_uid(card.uid)
    return f"{card.nickname} ({blur_uid(card.uid)})"


class StatsView(View):
    def __init__(self, record_cards: Sequence[RecordCard], *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self._record_cards = record_cards
        self.add_item(CardSelect(record_cards))

    def get_card(self, uid: int) -> RecordCard:
        return next(card for card in self._record_cards if card.uid == uid)

    def get_card_embed(self, card: RecordCard) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=get_label(card), description=LevelStr(card.level))
        for d in card.data:
            embed.add_field(name=d.name, value=d.value)
        embed.set_author(name=card.game_name, icon_url=card.game_logo)
        return embed


class CardSelect(Select[StatsView]):
    def __init__(self, record_cards: Sequence[RecordCard]) -> None:
        options = [
            SelectOption(
                label=get_label(card),
                value=str(card.uid),
                emoji=get_game_emoji(card.game),
                description=card.game_name,
                default=card.uid == record_cards[0].uid,
            )
            for card in record_cards
        ]
        super().__init__(options=options, placeholder=LocaleStr(key="stats.select_card"))

    async def callback(self, i: Interaction) -> None:
        card = self.view.get_card(int(self.values[0]))
        self.update_options_defaults()
        await i.response.edit_message(embed=self.view.get_card_embed(card), view=self.view)
