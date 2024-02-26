from typing import TYPE_CHECKING, Any

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.hoyo.hsr.yatta import YattaAPIClient
from hoyo_buddy.ui import Select, SelectOption, View

if TYPE_CHECKING:
    import yatta
    from discord import Locale, Member, User

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


class CharacterUI(View):
    def __init__(
        self,
        character_id: int,
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.selected_page = 0
        self._character_id = character_id

        self._main_skill_index = 0
        self._sub_skill_index = 0
        self._eidolon_index = 0
        self._story_index = 0

        self._main_skill_embeds: list["DefaultEmbed"] = []
        self._sub_skill_embeds: list["DefaultEmbed"] = []
        self._eidolon_embeds: list["DefaultEmbed"] = []
        self._story_embeds: list["DefaultEmbed"] = []
        self._character_embed: "DefaultEmbed | None" = None

        self._character_detail: "yatta.CharacterDetail | None" = None

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        async with YattaAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self._character_id)
            self._character_detail = character_detail

            self._character_embed = api.get_character_embed(character_detail)
            self._main_skill_embeds = [
                api.get_character_main_skill_embed(skill)
                for skill in character_detail.traces.main_skills
            ]
            self._sub_skill_embeds = [
                api.get_character_sub_skill_embed(skill)
                for skill in character_detail.traces.sub_skills
            ]
            self._eidolon_embeds = [
                api.get_character_eidolon_embed(skill) for skill in character_detail.eidolons
            ]
            self._story_embeds = [
                api.get_character_story_embed(story) for story in character_detail.script.stories
            ]

        await self._update(i, responded=True)

    async def _update(self, i: "INTERACTION", *, responded: bool = False) -> None:
        if self._character_detail is None:
            msg = "Character detail not fetched"
            raise RuntimeError(msg)

        self.clear_items()
        self.add_item(PageSelector(self.selected_page))

        match self.selected_page:
            case 0:
                embed = self._character_embed
            case 1:
                embed = self._main_skill_embeds[self._main_skill_index]
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=s.skill_list[0].name,
                                value=str(index),
                                default=index == self._main_skill_index,
                            )
                            for index, s in enumerate(self._character_detail.traces.main_skills)
                        ],
                        "_main_skill_index",
                    )
                )
            case 2:
                embed = self._eidolon_embeds[self._eidolon_index]
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=f"{index + 1}. {e.name}",
                                value=str(index),
                                default=index == self._eidolon_index,
                            )
                            for index, e in enumerate(self._character_detail.eidolons)
                        ],
                        "_eidolon_index",
                    )
                )
            case 3:
                embed = self._sub_skill_embeds[self._sub_skill_index]
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=s.name,
                                value=str(index),
                                default=index == self._sub_skill_index,
                            )
                            for index, s in enumerate(self._character_detail.traces.sub_skills)
                            if s.point_type == "Special" and s.name is not None
                        ],
                        "_sub_skill_index",
                    )
                )
            case 4:
                embed = self._story_embeds[self._story_index]
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=s.title,
                                value=str(index),
                                default=index == self._story_index,
                            )
                            for index, s in enumerate(self._character_detail.script.stories)
                        ],
                        "_story_index",
                    )
                )
            case _:
                msg = "Invalid page index"
                raise ValueError(msg)

        if responded:
            await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)


class PageSelector(Select["CharacterUI"]):
    def __init__(self, current: int) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr("Details", key="yatta_character_detail_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr("Skills", key="yatta_character_skill_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr("Eidolons", key="yatta_character_eidolon_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=LocaleStr("Traces", key="yatta_character_trace_page_label"),
                    value="3",
                    default=current == 3,
                ),
                SelectOption(
                    label=LocaleStr("Stories", key="character_stories_page_label"),
                    value="4",
                    default=current == 4,
                ),
            ],
            row=4,
        )

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view._update(i)


class ItemSelector(Select["CharacterUI"]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self._index_name = index_name

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.__setattr__(self._index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view._update(i)
