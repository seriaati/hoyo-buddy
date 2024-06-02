from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View
from hoyo_buddy.ui.components import PaginatorSelect

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
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.selected_page = 0
        self._character_id = character_id
        self._character_level = 80

        self._main_skill_index = 0
        self._main_skill_levels: list[int] = []
        self._sub_skill_index = 0
        self._eidolon_index = 0
        self._story_index = 0
        self._voice_index = 0

        self._main_skill_embeds: list[DefaultEmbed] = []
        self._sub_skill_embeds: list[DefaultEmbed] = []
        self._eidolon_embeds: list[DefaultEmbed] = []
        self._story_embeds: list[DefaultEmbed] = []
        self._voice_embeds: list[DefaultEmbed] = []
        self._character_embed: DefaultEmbed | None = None

        self._character_detail: yatta.CharacterDetail | None = None
        self._manual_avatar: dict[str, Any] | None = None

    async def start(self, i: INTERACTION) -> None:
        await i.response.defer()

        async with YattaAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self._character_id)
            manual_avatar = await api.fetch_manual_avatar()

            self._character_detail = character_detail
            self._manual_avatar = manual_avatar

            self._main_skill_levels = [
                skill.max_level for skill in character_detail.traces.main_skills
            ]

            self._character_embed = api.get_character_details_embed(
                character_detail, self._character_level, manual_avatar
            )
            self._main_skill_embeds = [
                api.get_character_main_skill_embed(skill, skill.max_level)
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
            self._voice_embeds = [
                api.get_character_voice_embed(voice, self._character_id)
                for voice in character_detail.script.voices
            ]

        await self.update(i, responded=True)
        self.message = await i.original_response()

    async def update(self, i: INTERACTION, *, responded: bool = False) -> None:
        if self._character_detail is None:
            msg = "Character detail not fetched"
            raise RuntimeError(msg)

        self.clear_items()
        self.add_item(PageSelector(self.selected_page))

        match self.selected_page:
            case 0:
                embed = self._character_embed
                self.add_item(
                    EnterCharacterLevel(
                        LocaleStr("Change character level", key="change_character_level_label")
                    )
                )
            case 1:
                embed = self._main_skill_embeds[self._main_skill_index]
                self.add_item(
                    EnterSkilLevel(
                        label=LocaleStr("Change skill level", key="change_skill_level_label"),
                        skill_max_level=self._character_detail.traces.main_skills[
                            self._main_skill_index
                        ].max_level,
                    )
                )
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=f"{s.skill_list[0].type}: {s.skill_list[0].name}",
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
            case 5:
                embed = self._voice_embeds[self._voice_index]
                self.add_item(
                    VoiceSelector(
                        options=[
                            SelectOption(
                                label=v.title,
                                value=str(index),
                                default=index == self._voice_index,
                            )
                            for index, v in enumerate(self._character_detail.script.voices)
                        ],
                    )
                )
            case _:
                msg = "Invalid page index"
                raise ValueError(msg)

        if responded:
            await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)

        self.message = await i.original_response()


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
                SelectOption(
                    label=LocaleStr("Voices", key="character_voices_page_label"),
                    value="5",
                    default=current == 5,
                ),
            ],
            row=4,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select["CharacterUI"]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self._index_name = index_name

    async def callback(self, i: INTERACTION) -> Any:
        self.view.__setattr__(self._index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view.update(i)


class SkillLevelModal(Modal):
    level = TextInput(
        label=LocaleStr("Level", key="level_label"),
        is_digit=True,
        min_value=1,
    )

    def __init__(self, max_level: int) -> None:
        super().__init__(title=LocaleStr("Enter Skill Level", key="skill_level.modal.title"))
        self.level.max_value = max_level


class EnterSkilLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr, skill_max_level: int) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)
        self._skill_max_level = skill_max_level

    async def callback(self, i: INTERACTION) -> Any:
        modal = SkillLevelModal(self._skill_max_level)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        incomplete = modal.incomplete
        if incomplete:
            return

        assert self.view._character_detail is not None
        assert self.view._main_skill_index is not None

        self.view._main_skill_levels[self.view._main_skill_index] = int(modal.level.value)
        async with YattaAPIClient(self.view.locale, self.view.translator) as api:
            self.view._main_skill_embeds[self.view._main_skill_index] = (
                api.get_character_main_skill_embed(
                    self.view._character_detail.traces.main_skills[self.view._main_skill_index],
                    self.view._main_skill_levels[self.view._main_skill_index],
                )
            )

        await self.view.update(i, responded=True)


class CharacterLevelModal(Modal):
    level = TextInput(
        label=LocaleStr("Level", key="level_label"),
        is_digit=True,
        min_value=1,
        max_value=80,
    )


class EnterCharacterLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: INTERACTION) -> Any:
        modal = CharacterLevelModal(
            title=LocaleStr("Enter Character Level", key="chara_level.modal.title")
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        incomplete = modal.incomplete
        if incomplete:
            return

        assert self.view._character_detail is not None
        assert self.view._manual_avatar is not None

        self.view._character_level = int(modal.level.value)
        async with YattaAPIClient(self.view.locale, self.view.translator) as api:
            self.view._character_embed = api.get_character_details_embed(
                self.view._character_detail, self.view._character_level, self.view._manual_avatar
            )

        await self.view.update(i, responded=True)


class VoiceSelector(PaginatorSelect[CharacterUI]):
    async def callback(self, i: INTERACTION) -> Any:
        await super().callback()
        try:
            self.view._voice_index = int(self.values[0])
        except ValueError:
            await i.response.edit_message(view=self.view)
        else:
            await self.view.update(i)
