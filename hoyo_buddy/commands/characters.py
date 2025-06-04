from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import hakushin

from hoyo_buddy.constants import locale_to_hakushin_lang
from hoyo_buddy.db.utils import draw_locale
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui.hoyo.characters import CharactersView

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.db import HoyoAccount, Settings
    from hoyo_buddy.types import Interaction


class CharactersCommand:
    def __init__(self, account: HoyoAccount, settings: Settings) -> None:
        self.account = account
        self.settings = settings

        self.element_char_counts = {}
        self.path_char_counts = {}

    async def run_gi(self) -> None:
        async with AmbrAPIClient() as client:
            self.element_char_counts = await client.fetch_element_char_counts()
            self.element_char_counts["none"] = 1

    async def run_hsr(self) -> None:
        async with YattaAPIClient() as client:
            self.element_char_counts = await client.fetch_element_char_counts()
            self.path_char_counts = await client.fetch_path_char_counts()

    async def run_zzz(self, locale: Locale) -> None:
        element_char_counts: defaultdict[str, int] = defaultdict(int)

        async with hakushin.HakushinAPI(
            hakushin.Game.ZZZ, locale_to_hakushin_lang(locale)
        ) as client:
            agents = await client.fetch_characters()

            for agent in agents:
                if agent.rarity is None or agent.element is None:
                    continue
                element_char_counts[agent.element.name.lower()] += 1

        self.element_char_counts = dict(element_char_counts)

    async def run(self, i: Interaction) -> None:
        account, settings = self.account, self.settings
        game = account.game
        locale = settings.locale or i.locale

        if game is Game.GENSHIN:
            await self.run_gi()
        elif game is Game.STARRAIL:
            await self.run_hsr()
        elif game is Game.ZZZ:
            await self.run_zzz(locale)

        draw_input = DrawInput(
            dark_mode=settings.dark_mode,
            locale=draw_locale(locale, account),
            session=i.client.session,
            filename="characters.png",
            executor=i.client.executor,
            loop=i.client.loop,
        )
        view = CharactersView(
            account,
            self.element_char_counts,
            self.path_char_counts,
            author=i.user,
            locale=locale,
            draw_input=draw_input,
        )
        await view.start(i)
