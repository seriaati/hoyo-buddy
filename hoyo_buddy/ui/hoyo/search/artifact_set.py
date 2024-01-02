import contextlib
from typing import TYPE_CHECKING

from discord import ButtonStyle, InteractionResponded, Locale, Member, User

from ....bot.emojis import ARTIFACT_POS_EMOJIS
from ....exceptions import InvalidQueryError
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...ui import Button, View

if TYPE_CHECKING:
    from ....bot import INTERACTION, Translator
    from ....embeds import DefaultEmbed


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
        self.pos_index = 0

    async def fetch_artifact_embeds(self) -> list["DefaultEmbed"]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            try:
                artifact_id = int(self.artifact_id)
            except ValueError as e:
                raise InvalidQueryError from e

            artifact_set_detail = await api.fetch_artifact_set_detail(artifact_id)

            return [
                api.get_artifact_embed(artifact_set_detail, artifact)
                for artifact in artifact_set_detail.artifacts
            ]

    async def update(self, i: "INTERACTION") -> None:
        with contextlib.suppress(InteractionResponded):
            await i.response.defer()

        self.clear_items()
        for pos in range(5):
            self.add_item(ArtifactPosButton(pos))

        embeds = await self.fetch_artifact_embeds()
        embed = embeds[self.pos_index]

        await i.edit_original_response(embed=embed, view=self)


class ArtifactPosButton(Button["ArtifactSetUI"]):
    def __init__(self, pos: int) -> None:
        super().__init__(style=ButtonStyle.blurple, emoji=list(ARTIFACT_POS_EMOJIS.values())[pos])
        self.pos = pos

    async def callback(self, i: "INTERACTION") -> None:
        self.view.pos_index = self.pos
        await self.view.update(i)
