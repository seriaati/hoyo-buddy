from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.ui import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ambr.models import CardTalent, TCGCardDetail
    from discord import Locale, Member, User

    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction


class TCGCardUI(View):
    def __init__(
        self,
        card_id: int,
        *,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.card_id = card_id
        self.card_embed: DefaultEmbed | None = None
        self.card: TCGCardDetail | None = None

        self.dictionary_embed: DefaultEmbed | None = None

        self.talent_embeds: dict[str, DefaultEmbed] = {}
        self.current_talent_id: str | None = None

    def _setup_items(self) -> None:
        card = self.card
        if card is None:
            return

        self.clear_items()
        self.add_item(ViewCardButton())
        if card.dictionaries:
            self.add_item(ViewDictionaryButton())
        if card.talents:
            self.add_item(CardTalentSelector(card.talents, self.current_talent_id))

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        async with AmbrAPIClient(self.locale, self.translator) as api:
            card = await api.fetch_tcg_card_detail(self.card_id)
            self.card = card
            if card.talents:
                for talent in card.talents:
                    self.talent_embeds[talent.id] = api.get_tcg_card_talent_embed(
                        talent, card.dictionaries
                    )
            if card.dictionaries:
                self.dictionary_embed = api.get_tcg_card_dictionaries_embed(card.dictionaries)
            self.card_embed = api.get_tcg_card_embed(card)

        self._setup_items()
        self.message = await i.edit_original_response(embed=self.card_embed, view=self)


class ViewCardButton(Button[TCGCardUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="view_card_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> None:
        if self.view.card_embed is None:
            return

        self.view.current_talent_id = None
        self.view._setup_items()
        await i.response.edit_message(embed=self.view.card_embed, view=self.view)


class ViewDictionaryButton(Button[TCGCardUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="view_dictionary_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> None:
        if self.view.dictionary_embed is None:
            return

        self.view.current_talent_id = None
        self.view._setup_items()
        await i.response.edit_message(embed=self.view.dictionary_embed, view=self.view)


class CardTalentSelector(Select[TCGCardUI]):
    def __init__(
        self,
        talents: list[CardTalent],
        current_talent_id: str | None = None,
    ) -> None:
        super().__init__(
            placeholder="Select a talent to view",
            options=[
                SelectOption(label=t.name or "???", value=t.id, default=current_talent_id == t.id)
                for t in talents
            ],
        )
        self.talents = talents

    async def callback(self, i: Interaction) -> None:
        talent_id = self.view.current_talent_id = self.values[0]
        talent_embed = self.view.talent_embeds.get(talent_id)
        if talent_embed is None:
            return

        self.view._setup_items()
        await i.response.edit_message(embed=talent_embed, view=self.view)
