from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import Settings
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients import ambr
from hoyo_buddy.ui.hoyo.genshin.build import GIBuildView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class BuildCommand:
    def __init__(self, game: Game, character_id: str) -> None:
        self.game = game
        self.character_id = character_id

    async def run_gi(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        settings = await Settings.get(user_id=i.user.id)
        locale = settings.locale or i.locale
        dark_mode = settings.dark_mode

        async with ambr.AmbrAPIClient(locale) as client:
            guide = await client.fetch_character_guide(self.character_id)
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()
            artifact_sets = await client.fetch_artifact_sets()

        view = GIBuildView(
            self.character_id,
            guide,
            characters,
            weapons,
            artifact_sets,
            dark_mode=dark_mode,
            author=i.user,
            locale=locale,
        )
        await view.start(i)

    async def run_hsr(self, i: Interaction) -> None:
        pass

    async def run_zzz(self, i: Interaction) -> None:
        pass

    async def run(self, i: Interaction) -> None:
        if self.game is Game.GENSHIN:
            await self.run_gi(i)
        elif self.game is Game.STARRAIL:
            await self.run_hsr(i)
        elif self.game is Game.ZZZ:
            await self.run_zzz(i)
