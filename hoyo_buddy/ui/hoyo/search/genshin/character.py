import contextlib
from typing import TYPE_CHECKING, Any

from discord import InteractionResponded, Locale, Member, User

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.hoyo.genshin.ambr import AmbrAPIClient
from hoyo_buddy.ui import LevelModalButton, PaginatorSelect, Select, SelectOption, View

if TYPE_CHECKING:
    import ambr

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


class CharacterUI(View):
    def __init__(
        self,
        character_id: str,
        *,
        author: User | Member,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.character_id = character_id
        self.character_level = 90
        self.talent_index = 0
        self.talent_level = 10
        self.const_index = 0
        self.story_index = 0
        self.quote_index = 0
        self.selected_page = 0

    async def fetch_character_embed(self) -> "DefaultEmbed":
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

    async def fetch_talent_embed(self) -> tuple["DefaultEmbed", bool, list["ambr.Talent"]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            talent = character_detail.talents[self.talent_index]
            talent_max_level = self.talent_level if talent.upgrades else 0
            return (
                api.get_character_talent_embed(talent, talent_max_level),
                bool(talent.upgrades),
                character_detail.talents,
            )

    async def fetch_const_embed(self) -> tuple["DefaultEmbed", list["ambr.Constellation"]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            const = character_detail.constellations[self.const_index]
            return (
                api.get_character_constellation_embed(const),
                character_detail.constellations,
            )

    async def fetch_story_embed(self) -> tuple["DefaultEmbed", list["ambr.Story"]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            story = character_fetter.stories[self.story_index]
            return (
                api.get_character_story_embed(story),
                character_fetter.stories,
            )

    async def fetch_quote_embed(self) -> tuple["DefaultEmbed", list["ambr.Quote"]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            quote = character_fetter.quotes[self.quote_index]
            return (
                api.get_character_quote_embed(quote, self.character_id),
                character_fetter.quotes,
            )

    async def update(self, i: "INTERACTION") -> None:
        with contextlib.suppress(InteractionResponded):
            await i.response.defer()

        self.clear_items()
        self.add_item(PageSelector(self.selected_page))

        match self.selected_page:
            case 0:
                embed = await self.fetch_character_embed()
                self.add_item(
                    CharacterLevelModalButton(
                        True,
                        min_level=1,
                        max_level=90,
                        default=self.character_level,
                        label=LocaleStr(
                            "Change character level", key="change_character_level_label"
                        ),
                    )
                )
            case 1:
                embed, upgradeable, talents = await self.fetch_talent_embed()
                if upgradeable:
                    self.add_item(
                        CharacterLevelModalButton(
                            False,
                            min_level=1,
                            max_level=10,
                            default=self.talent_level,
                            label=LocaleStr("Change talent level", key="change_talent_level_label"),
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
            case 2:
                embed, consts = await self.fetch_const_embed()
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=f"{i + 1}. {c.name}",
                                value=str(i),
                                default=i == self.const_index,
                            )
                            for i, c in enumerate(consts)
                        ],
                        "const_index",
                    )
                )
            case 3:
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
            case 4:
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
            case _:
                msg = f"Invalid page index: {self.selected_page}"
                raise ValueError(msg)

        await i.edit_original_response(embed=embed, view=self)


class CharacterLevelModalButton(LevelModalButton["CharacterUI"]):
    def __init__(
        self,
        is_character_level: bool,
        *,
        min_level: int,
        max_level: int,
        default: int | None = None,
        label: LocaleStr,
    ) -> None:
        super().__init__(
            min_level=min_level, max_level=max_level, default_level=default, label=label
        )
        self.is_character_level = is_character_level

    async def callback(self, i: "INTERACTION") -> Any:
        await super().callback(i)
        if self.is_character_level:
            self.view.character_level = self.level
        else:
            self.view.talent_level = self.level
        await self.view.update(i)


class PageSelector(Select["CharacterUI"]):
    def __init__(self, current: int) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr("Profile", key="character_profile_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr("Talents", key="character_talents_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr("Constellations", key="character_const_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=LocaleStr("Stories", key="character_stories_page_label"),
                    value="3",
                    default=current == 3,
                ),
                SelectOption(
                    label=LocaleStr("Quotes", key="character_quotes_page_label"),
                    value="4",
                    default=current == 4,
                ),
            ],
            row=4,
        )

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select["CharacterUI"]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self.index_name = index_name

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.__setattr__(self.index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view.update(i)


class QuoteSelector(PaginatorSelect["CharacterUI"]):
    async def callback(self, i: "INTERACTION") -> Any:
        await super().callback()
        try:
            self.view.quote_index = int(self.values[0])
        except ValueError:
            await i.response.edit_message(view=self.view)
        else:
            await self.view.update(i)
