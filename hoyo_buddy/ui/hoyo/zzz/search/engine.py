from __future__ import annotations

from typing import TYPE_CHECKING

import hakushin

from hoyo_buddy.constants import locale_to_hakushin_lang
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.ui import View
from hoyo_buddy.ui.components import Select, SelectOption
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.types import Interaction, User

__all__ = ("EngineSearchView",)


class EngineSearchView(View):
    def __init__(
        self, engine_id: int, *, author: User, locale: Locale, translator: Translator
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self._engine_id = engine_id
        self._engine: hakushin.zzz.WeaponDetail
        self._hakushin_translator = HakushinTranslator(locale, translator)
        self._refinement: str = "1"

    def _add_items(self) -> None:
        self.add_item(RefinementSelect(self._refinement))

    async def _fetch_data(self) -> None:
        async with hakushin.HakushinAPI(
            hakushin.Game.ZZZ, locale_to_hakushin_lang(self.locale)
        ) as api:
            self._engine = await api.fetch_weapon_detail(self._engine_id)

    async def update(self, i: Interaction) -> None:
        embed = self._hakushin_translator.get_engine_embed(self._engine, self._refinement)
        if i.response.is_done():
            await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        await self._fetch_data()
        self._add_items()
        await self.update(i)


class RefinementSelect(Select[EngineSearchView]):
    def __init__(self, current: str) -> None:
        refinements = (1, 2, 3, 4, 5)
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(key="refinement_indicator", r=r),
                    value=str(r),
                    default=r == int(current),
                )
                for r in refinements
            ],
            placeholder=LocaleStr(key="zzz.engine.refinement_select.placeholder"),
        )

    async def callback(self, i: Interaction) -> None:
        self.view._refinement = self.values[0]
        await self.view.update(i)
