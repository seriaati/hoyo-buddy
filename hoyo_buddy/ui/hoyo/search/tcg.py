from typing import TYPE_CHECKING

from discord import ButtonStyle

from ....bot.translator import LocaleStr
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...ui import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from ambr.models import CardTalent
    from discord import Locale, Member, User

    from ....bot.bot import INTERACTION
    from ....bot.translator import Translator
    from ....embeds import DefaultEmbed


class TCGCardUI(View):
    def __init__(
        self,
        card_id: int,
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.card_id = card_id
        self.card_embed: "DefaultEmbed | None" = None
        self.dictionary_embed: "DefaultEmbed | None" = None
        self.talent_embeds: dict[str, "DefaultEmbed"] = {}

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        async with AmbrAPIClient(self.locale, self.translator) as api:
            card = await api.fetch_tcg_card_detail(self.card_id)

            self.add_item(ViewCardButton())
            if card.talents:
                for talent in card.talents:
                    self.talent_embeds[talent.id] = api.get_tcg_card_talent_embed(
                        talent, card.dictionaries
                    )
                self.add_item(CardTalentSelector(card.talents))

            if card.dictionaries:
                self.dictionary_embed = api.get_tcg_card_dictionaries_embed(card.dictionaries)
                self.add_item(ViewDictionaryButton())

            self.card_embed = api.get_tcg_card_embed(card)
            await i.edit_original_response(embed=self.card_embed, view=self)


class ViewCardButton(Button["TCGCardUI"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Card", key="view_card_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: "INTERACTION") -> None:
        if self.view.card_embed is None:
            msg = "Call `TCGCardUI.start` before using this button"
            raise RuntimeError(msg)

        await i.response.edit_message(embed=self.view.card_embed)


class ViewDictionaryButton(Button["TCGCardUI"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Dictionary", key="view_dictionary_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: "INTERACTION") -> None:
        if self.view.dictionary_embed is None:
            msg = "Call `TCGCardUI.start` before using this button"
            raise RuntimeError(msg)

        await i.response.edit_message(embed=self.view.dictionary_embed)


class CardTalentSelector(Select["TCGCardUI"]):
    def __init__(
        self,
        talents: list["CardTalent"],
    ) -> None:
        super().__init__(
            placeholder="Select a talent to view",
            options=[SelectOption(label=t.name or "???", value=t.id) for t in talents],
        )
        self.talents = talents

    async def callback(self, i: "INTERACTION") -> None:
        talent_id = self.values[0]
        talent_embed = self.view.talent_embeds.get(talent_id)
        if talent_embed is None:
            msg = f"Invalid talent ID: {talent_id}"
            raise RuntimeError(msg)

        await i.response.edit_message(embed=talent_embed)
