from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.emojis import get_relic_pos_emoji
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.hakushin import HakushinAPI
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui import Button, View

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed

RELIC_POS: tuple[str, ...] = ("neck", "head", "hand", "object", "foot", "body")


class RelicSetUI(View):
    def __init__(
        self,
        relic_set_id: str,
        *,
        hakushin: bool,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self._relic_set_id = relic_set_id
        self._relic_embeds: dict[str, DefaultEmbed] = {}

        self._hakushin = hakushin

    async def start(self, i: INTERACTION) -> None:
        await i.response.defer()

        try:
            relic_id = int(self._relic_set_id)
        except ValueError as e:
            raise InvalidQueryError from e

        if self._hakushin:
            async with HakushinAPI(self.locale, self.translator) as api:
                relic_set_detail = await api.fetch_relic_set_detail(relic_id)

                self._relic_embeds = {
                    RELIC_POS[index]: api.get_relic_embed(relic_set_detail, relic)
                    for index, relic in enumerate(relic_set_detail.parts.values())
                }
        else:
            async with YattaAPIClient(self.locale, self.translator) as api:
                relic_set_detail = await api.fetch_relic_set_detail(relic_id)

                self._relic_embeds = {
                    relic.pos: api.get_relic_embed(relic_set_detail, relic)
                    for relic in relic_set_detail.relics
                }

        for pos in self._relic_embeds:
            self.add_item(RelicPosButton(pos))

        await i.edit_original_response(embed=next(iter(self._relic_embeds.values())), view=self)
        self.message = await i.original_response()


class RelicPosButton(Button["RelicSetUI"]):
    def __init__(self, pos: str) -> None:
        super().__init__(style=ButtonStyle.blurple, emoji=get_relic_pos_emoji(pos))
        self.pos = pos

    async def callback(self, i: INTERACTION) -> None:
        await i.response.edit_message(embed=self.view._relic_embeds[self.pos])
