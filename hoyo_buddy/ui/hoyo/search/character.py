import contextlib
from typing import Any, List, Optional, Tuple, Union

import ambr
from discord import InteractionResponded, Locale, Member, User

from ....bot import INTERACTION, Translator
from ....bot.translator import locale_str as _T
from ....embeds import DefaultEmbed
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...ui import LevelModalButton as LMB
from ...ui import PaginatorSelect, Select, SelectOption, View


class CharacterUI(View):
    def __init__(
        self,
        character_id: str,
        *,
        author: Union[User, Member],
        locale: Locale,
        translator: Translator,
    ):
        super().__init__(author=author, locale=locale, translator=translator)
        self.character_id = character_id
        self.character_level = 90
        self.talent_index = 0
        self.talent_level = 10
        self.const_index = 0
        self.story_index = 0
        self.quote_index = 0
        self.selected = 0

    async def fetch_character_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            avatar_curve = await api.fetch_avatar_curve()
            manual_weapon = await api.fetch_manual_weapon()
            return api.get_character_embed(
                character_detail,
                self.character_level,
                avatar_curve,
                manual_weapon,
            )

    async def fetch_talent_embed(self) -> Tuple[DefaultEmbed, bool, List[ambr.Talent]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            talent = character_detail.talents[self.talent_index]
            talent_max_level = self.talent_level if talent.upgrades else 0
            return (
                api.get_character_talent_embed(talent, talent_max_level),
                bool(talent.upgrades),
                character_detail.talents,
            )

    async def fetch_const_embed(self) -> Tuple[DefaultEmbed, List[ambr.Constellation]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            const = character_detail.constellations[self.const_index]
            return (
                api.get_character_constellation_embed(const),
                character_detail.constellations,
            )

    async def fetch_story_embed(self) -> Tuple[DefaultEmbed, List[ambr.Story]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            story = character_fetter.stories[self.story_index]
            return (
                api.get_character_story_embed(story),
                character_fetter.stories,
            )

    async def fetch_quote_embed(self) -> Tuple[DefaultEmbed, List[ambr.Quote]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            quote = character_fetter.quotes[self.quote_index]
            return (
                api.get_character_quote_embed(quote, self.character_id),
                character_fetter.quotes,
            )

    async def update(self, i: INTERACTION) -> None:
        with contextlib.suppress(InteractionResponded):
            await i.response.defer()

        self.clear_items()
        self.add_item(PageSelector(self.selected))

        if self.selected == 0:
            embed = await self.fetch_character_embed()
            self.add_item(
                LevelModalButton(
                    True,
                    min_level=1,
                    max_level=90,
                    default=self.character_level,
                    label=_T("Change character level", key="change_character_level_label"),
                )
            )
        elif self.selected == 1:
            embed, upgradeable, talents = await self.fetch_talent_embed()
            if upgradeable:
                self.add_item(
                    LevelModalButton(
                        False,
                        min_level=1,
                        max_level=10,
                        default=self.talent_level,
                        label=_T("Change talent level", key="change_talent_level_label"),
                    )
                )
            self.add_item(
                ItemSelector(
                    [
                        SelectOption(
                            label=t.name,
                            value=str(i),
                            default=i == self.talent_index,
                        )
                        for i, t in enumerate(talents)
                    ],
                    "talent_index",
                )
            )
        elif self.selected == 2:
            embed, consts = await self.fetch_const_embed()
            self.add_item(
                ItemSelector(
                    [
                        SelectOption(
                            label=f"{i+1}. {c.name}",
                            value=str(i),
                            default=i == self.const_index,
                        )
                        for i, c in enumerate(consts)
                    ],
                    "const_index",
                )
            )
        elif self.selected == 3:
            embed, stories = await self.fetch_story_embed()
            self.add_item(
                ItemSelector(
                    [
                        SelectOption(
                            label=s.title,
                            value=str(i),
                            default=i == self.story_index,
                        )
                        for i, s in enumerate(stories)
                    ],
                    "story_index",
                )
            )
        elif self.selected == 4:
            embed, quotes = await self.fetch_quote_embed()
            self.add_item(
                QuoteSelector(
                    [
                        SelectOption(
                            label=q.title,
                            value=str(i),
                            default=i == self.quote_index,
                        )
                        for i, q in enumerate(quotes)
                    ]
                )
            )
        else:
            raise NotImplementedError

        await i.edit_original_response(embed=embed, view=self)


class LevelModalButton(LMB):
    def __init__(
        self,
        is_character_level: bool,
        *,
        min_level: int,
        max_level: int,
        default: Optional[int] = None,
        label: _T,
    ):
        super().__init__(
            min_level=min_level, max_level=max_level, default_level=default, label=label
        )
        self.is_character_level = is_character_level

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CharacterUI
        await super().callback(i)
        if self.is_character_level:
            self.view.character_level = self.level
        else:
            self.view.talent_level = self.level
        await self.view.update(i)


class PageSelector(Select):
    def __init__(self, current: int):
        super().__init__(
            options=[
                SelectOption(
                    label=_T("Profile", key="character_profile_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=_T("Talents", key="character_talents_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=_T("Constellations", key="character_const_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=_T("Stories", key="character_stories_page_label"),
                    value="3",
                    default=current == 3,
                ),
                SelectOption(
                    label=_T("Quotes", key="character_quotes_page_label"),
                    value="4",
                    default=current == 4,
                ),
            ],
            row=4,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CharacterUI
        self.view.selected = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select):
    def __init__(self, options: List[SelectOption], index_name: str):
        super().__init__(options=options)
        self.index_name = index_name

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CharacterUI
        self.view.__setattr__(self.index_name, int(self.values[0]))
        await self.view.update(i)


class QuoteSelector(PaginatorSelect):
    async def callback(self, i: INTERACTION) -> Any:
        await super().callback()
        self.view: CharacterUI
        try:
            self.view.quote_index = int(self.values[0])
        except ValueError:
            await i.response.edit_message(view=self.view)
        else:
            await self.view.update(i)
