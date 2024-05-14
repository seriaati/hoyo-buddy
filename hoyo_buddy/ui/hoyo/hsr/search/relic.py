from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.emojis import get_relic_pos_emoji
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.yatta_client import YattaAPIClient
from hoyo_buddy.ui import Button, View

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


class RelicSetUI(View):
    def __init__(
        self,
        relic_set_id: str,
        *,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.relic_set_id = relic_set_id
        self.relic_embeds: dict[str, DefaultEmbed] = {}

    async def start(self, i: INTERACTION) -> None:
        await i.response.defer()

        async with YattaAPIClient(self.locale, self.translator) as api:
            try:
                relic_id = int(self.relic_set_id)
            except ValueError as e:
                raise InvalidQueryError from e

            relic_set_detail = await api.fetch_relic_set_detail(relic_id)

            self.relic_embeds = {
                relic.pos: api.get_relic_embed(relic_set_detail, relic)
                for relic in relic_set_detail.relics
            }

        for artifact in relic_set_detail.relics:
            self.add_item(RelicPosButton(artifact.pos))

        await i.edit_original_response(
            embed=self.relic_embeds[relic_set_detail.relics[0].pos], view=self
        )


class RelicPosButton(Button["RelicSetUI"]):
    def __init__(self, pos: str) -> None:
        super().__init__(style=ButtonStyle.blurple, emoji=get_relic_pos_emoji(pos))
        self.pos = pos

    async def callback(self, i: INTERACTION) -> None:
        await i.response.edit_message(embed=self.view.relic_embeds[self.pos])
