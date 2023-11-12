from typing import Any, List, Tuple

import ambr
from discord import Interaction, InteractionResponded

from ....bot.translator import locale_str as _T
from ....embeds import DefaultEmbed
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...ui import LevelModalButton as LMB
from ...ui import Select, SelectOption, View


class CharacterUI(View):
    def __init__(self, api: AmbrAPIClient, character_id: str):
        self.api = api
        self.character_id = character_id
        self.character_level = 90
        self.talent_index = 0
        self.talent_level = 10
        self.const_index = 0
        self.selected = 0

    async def fetch_character_embed(self) -> DefaultEmbed:
        character_detail = await self.api.fetch_character_detail(self.character_id)
        avatar_curve = await self.api.fetch_avatar_curve()
        manual_weapon = await self.api.fetch_manual_weapon()
        return self.api.get_character_embed(
            character_detail,
            self.character_level,
            avatar_curve,
            manual_weapon,
        )

    async def fetch_talent_embed(self) -> Tuple[DefaultEmbed, bool, List[ambr.Talent]]:
        character_detail = await self.api.fetch_character_detail(self.character_id)
        talent = character_detail.talents[self.talent_index]
        talent_max_level = self.talent_level if talent.upgrades else 0
        return (
            self.api.get_character_talent_embed(talent, talent_max_level),
            bool(talent.upgrades),
            character_detail.talents,
        )

    async def fetch_const_embed(self) -> Tuple[DefaultEmbed, List[ambr.Constellation]]:
        character_detail = await self.api.fetch_character_detail(self.character_id)
        const = character_detail.constellations[self.const_index]
        return (
            self.api.get_character_constellation_embed(const),
            character_detail.constellations,
        )

    async def update(self, i: Interaction) -> None:
        try:
            await i.response.defer()
        except InteractionResponded:
            pass
        self.clear_items()

        if self.selected == 0:
            embed = await self.fetch_character_embed()
            self.add_item(LevelModalButton(min=1, max=90, default=self.character_level))
        elif self.selected == 1:
            embed, upgradeable, talents = await self.fetch_talent_embed()
            if upgradeable:
                self.add_item(
                    LevelModalButton(min=1, max=10, default=self.talent_level)
                )
                self.add_item(
                    TalentConstSelector(
                        [
                            SelectOption(
                                label=_T(t.name, translate=False), value=str(i)
                            )
                            for i, t in enumerate(talents)
                        ],
                        is_const=False,
                    )
                )
        elif self.selected == 2:
            embed, consts = await self.fetch_const_embed()
            self.add_item(
                TalentConstSelector(
                    [
                        SelectOption(label=_T(c.name, translate=False), value=str(i))
                        for i, c in enumerate(consts)
                    ],
                    is_const=True,
                )
            )
        else:
            raise NotImplementedError

        await i.edit_original_response(embed=embed, view=self)


class LevelModalButton(LMB):
    async def callback(self, i: Interaction) -> Any:
        self.view: CharacterUI
        await super().callback(i)
        await self.view.update(i)


class PageSelector(Select):
    def __init__(self):
        super().__init__(
            options=[
                SelectOption(
                    label=_T("Profile", warn_no_key=False), value="0", default=True
                ),
                SelectOption(label=_T("Talents", warn_no_key=False), value="1"),
                SelectOption(label=_T("Constellations", warn_no_key=False), value="2"),
            ],
        )

    async def callback(self, i: Interaction) -> Any:
        self.view: CharacterUI
        self.selected = int(self.values[0])
        await self.view.update(i)


class TalentConstSelector(Select):
    def __init__(self, options: List[SelectOption], is_const: bool):
        super().__init__(options=options)
        self.is_const = is_const

    async def callback(self, i: Interaction) -> Any:
        self.view: CharacterUI
        if self.is_const:
            self.view.const_index = int(self.values[0])
        else:
            self.view.talent_index = int(self.values[0])
        await self.view.update(i)
