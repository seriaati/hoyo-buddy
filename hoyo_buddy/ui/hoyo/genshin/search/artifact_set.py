from __future__ import annotations

from typing import TYPE_CHECKING

import hakushin
from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.constants import EQUIP_ID_TO_ARTIFACT_POS, locale_to_hakushin_lang
from hoyo_buddy.emojis import get_artifact_pos_emoji
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.ui import Button, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction


class ArtifactSetUI(View):
    def __init__(
        self, artifact_set_id: str, *, hakushin: bool, author: User | Member, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)
        self._artifact_id = artifact_set_id
        self._artifact_embeds: dict[str, DefaultEmbed] = {}

        self._hakushin = hakushin

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        try:
            artifact_id = int(self._artifact_id)
        except ValueError as e:
            raise InvalidQueryError from e

        if self._hakushin:
            async with hakushin.HakushinAPI(
                hakushin.Game.GI, locale_to_hakushin_lang(self.locale)
            ) as api:
                artifact_set_detail = await api.fetch_artifact_set_detail(artifact_id)

                translator = HakushinTranslator(self.locale)
                self._artifact_embeds = {
                    pos: translator.get_artifact_embed(artifact_set_detail, artifact)
                    for pos, artifact in artifact_set_detail.parts.items()
                }
        else:
            async with AmbrAPIClient(self.locale) as api:
                artifact_set_detail = await api.fetch_artifact_set_detail(artifact_id)

                self._artifact_embeds = {
                    artifact.pos: api.get_artifact_embed(artifact_set_detail, artifact)
                    for artifact in artifact_set_detail.artifacts
                }

        for pos in self._artifact_embeds:
            self.add_item(ArtifactPosButton(pos))

        self.message = await i.edit_original_response(
            embed=next(iter(self._artifact_embeds.values())), view=self
        )


class ArtifactPosButton(Button["ArtifactSetUI"]):
    def __init__(self, pos: str) -> None:
        super().__init__(
            style=ButtonStyle.blurple, emoji=get_artifact_pos_emoji(EQUIP_ID_TO_ARTIFACT_POS[pos])
        )
        self.pos = pos

    async def callback(self, i: Interaction) -> None:
        await i.response.edit_message(embed=self.view._artifact_embeds[self.pos])
