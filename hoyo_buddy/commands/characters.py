from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from hoyo_buddy.constants import ZZZ_AGENT_DATA_URL
from hoyo_buddy.db.models import HoyoAccount, JSONFile, Settings
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui.hoyo.characters import CharactersView

if TYPE_CHECKING:
    import aiohttp

    from hoyo_buddy.types import Interaction


class CharactersCommand:
    def __init__(self, account: HoyoAccount, settings: Settings) -> None:
        self.account = account
        self.settings = settings

        self.element_char_counts = {}
        self.path_char_counts = {}
        self.faction_char_counts = {}

    async def run_gi(self) -> None:
        async with AmbrAPIClient() as client:
            self.element_char_counts = await client.fetch_element_char_counts()

    async def run_hsr(self) -> None:
        async with YattaAPIClient() as client:
            self.element_char_counts = await client.fetch_element_char_counts()
            self.path_char_counts = await client.fetch_path_char_counts()

    async def run_zzz(self, session: aiohttp.ClientSession) -> None:
        agent_data: dict[str, Any] = await JSONFile.fetch_and_cache(
            session, url=ZZZ_AGENT_DATA_URL, filename="zzz_agent_data.json"
        )

        element_char_counts: defaultdict[str, int] = defaultdict(int)
        faction_char_counts: defaultdict[str, int] = defaultdict(int)

        for agent in agent_data.values():
            if agent["beta"]:
                continue
            element_char_counts[agent["element"].lower()] += 1
            faction_char_counts[agent["faction"].lower()] += 1

        self.element_char_counts = dict(element_char_counts)
        self.faction_char_counts = dict(faction_char_counts)

    async def run(self, i: Interaction) -> None:
        account, settings = self.account, self.settings
        game = account.game

        if game is Game.GENSHIN:
            await self.run_gi()
        elif game is Game.STARRAIL:
            await self.run_hsr()
        elif game is Game.ZZZ:
            await self.run_zzz(i.client.session)

        view = CharactersView(
            account,
            settings.dark_mode,
            self.element_char_counts,
            self.path_char_counts,
            self.faction_char_counts,
            session=i.client.session,
            executor=i.client.executor,
            loop=i.client.loop,
            author=i.user,
            locale=settings.locale or i.locale,
        )
        await view.start(i)
