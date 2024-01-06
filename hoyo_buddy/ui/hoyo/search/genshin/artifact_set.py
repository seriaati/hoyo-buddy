from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.bot.emojis import ARTIFACT_POS_EMOJIS
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.genshin.ambr import AmbrAPIClient
from hoyo_buddy.ui import Button, View

from .....bot.constants import EQUIP_ID_TO_ARTIFACT_POS

if TYPE_CHECKING:
    from hoyo_buddy.bot import INTERACTION, Translator
    from hoyo_buddy.embeds import DefaultEmbed


class ArtifactSetUI(View):
    def __init__(
        self,
        artifact_set_id: str,
        *,
        author: User | Member,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.artifact_id = artifact_set_id
        self.artifact_embeds: dict[str, DefaultEmbed] = {}

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        async with AmbrAPIClient(self.locale, self.translator) as api:
            try:
                artifact_id = int(self.artifact_id)
            except ValueError as e:
                raise InvalidQueryError from e

            artifact_set_detail = await api.fetch_artifact_set_detail(artifact_id)

            self.artifact_embeds = {
                artifact.pos: api.get_artifact_embed(artifact_set_detail, artifact)
                for artifact in artifact_set_detail.artifacts
            }

        for artifact in artifact_set_detail.artifacts:
            self.add_item(ArtifactPosButton(artifact.pos))

        await i.edit_original_response(
            embed=self.artifact_embeds[artifact_set_detail.artifacts[0].pos], view=self
        )


class ArtifactPosButton(Button["ArtifactSetUI"]):
    def __init__(self, pos: str) -> None:
        super().__init__(
            style=ButtonStyle.blurple, emoji=ARTIFACT_POS_EMOJIS[EQUIP_ID_TO_ARTIFACT_POS[pos]]
        )
        self.pos = pos

    async def callback(self, i: "INTERACTION") -> None:
        await i.response.edit_message(embed=self.view.artifact_embeds[self.pos])
