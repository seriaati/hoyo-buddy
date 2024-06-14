from __future__ import annotations

from typing import TYPE_CHECKING, Any

import hakushin
import yatta
from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.constants import HAKUSHIN_HSR_SKILL_TYPE_NAMES
from hoyo_buddy.hoyo.clients.hakushin import HakushinAPI
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View
from hoyo_buddy.ui.components import PaginatorSelect

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.bot.bot import Interaction
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


class CharacterUI(View):
    def __init__(
        self,
        character_id: int,
        *,
        hakushin: bool,
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

        self._character_detail: yatta.CharacterDetail | hakushin.hsr.CharacterDetail | None = None
        self._manual_avatar: dict[str, Any] | None = None

        self._hakushin = hakushin

    @staticmethod
    def _convert_manual_avatar(manual_avatar: dict[str, dict[str, str]]) -> dict[str, str]:
        return {stat_id: stat["name"] for stat_id, stat in manual_avatar.items()}

    async def start(self, i: Interaction) -> None:
        await i.response.defer()

        if self._hakushin:
            async with YattaAPIClient(self.locale, self.translator) as api:
                manual_avatar = await api.fetch_manual_avatar()

            async with HakushinAPI(self.locale, self.translator) as api:
                character_detail = await api.fetch_character_detail(
                    self._character_id, hakushin.Game.HSR
                )

            self._character_detail = character_detail
            self._manual_avatar = manual_avatar

            self._main_skill_levels = [
                skill.max_level for skill in character_detail.skills.values()
            ]

            self._character_embed = api.get_character_embed(
                character_detail,
                self._character_level,
                self._convert_manual_avatar(manual_avatar),
            )

            self._main_skill_embeds = [
                api.get_character_skill_embed(skill, skill.max_level)
                for skill in character_detail.skills.values()
            ]
            self._eidolon_embeds = [
                api.get_character_eidolon_embed(eidolon)
                for eidolon in character_detail.eidolons.values()
            ]
        else:
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
                    api.get_character_story_embed(story)
                    for story in character_detail.script.stories
                ]
                self._voice_embeds = [
                    api.get_character_voice_embed(voice, self._character_id)
                    for voice in character_detail.script.voices
                ]

        await self.update(i)
        self.message = await i.original_response()

    async def update(self, i: Interaction) -> None:  # noqa: PLR0912, PLR0915
        if self._character_detail is None:
            msg = "Character detail not fetched"
            raise RuntimeError(msg)

        self.clear_items()
        self.add_item(PageSelector(self.selected_page, self._hakushin))

        if isinstance(self._character_detail, yatta.CharacterDetail):
            match self.selected_page:
                case 0:
                    embed = self._character_embed
                    self.add_item(
                        EnterCharacterLevel(LocaleStr(key="change_character_level_label"))
                    )
                case 1:
                    embed = self._main_skill_embeds[self._main_skill_index]
                    self.add_item(
                        EnterSkilLevel(
                            label=LocaleStr(key="change_skill_level_label"),
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
                                    label=f"{s.skill_list[0].type}: {s.skill_list[0].name}",
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
        else:
            match self.selected_page:
                case 0:
                    embed = self._character_embed
                    self.add_item(
                        EnterCharacterLevel(LocaleStr(key="change_character_level_label"))
                    )
                case 1:
                    embed = self._main_skill_embeds[self._main_skill_index]
                    self.add_item(
                        EnterSkilLevel(
                            label=LocaleStr(key="change_skill_level_label"),
                            skill_max_level=list(self._character_detail.skills.values())[
                                self._main_skill_index
                            ].max_level,
                        )
                    )

                    options: list[SelectOption] = []
                    skills = list(self._character_detail.skills.values())
                    skills.sort(key=lambda s: s.type or "Talent", reverse=True)
                    for index, skill in enumerate(skills):
                        type_str_key = HAKUSHIN_HSR_SKILL_TYPE_NAMES.get(skill.type or "Talent")
                        type_str = LocaleStr(key=type_str_key).translate(
                            self.translator, self.locale
                        )
                        options.append(
                            SelectOption(
                                label=f"{type_str}: {skill.name}",
                                value=str(index),
                                default=index == self._main_skill_index,
                            )
                        )
                    self.add_item(ItemSelector(options, "_main_skill_index"))
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
                                for index, e in enumerate(self._character_detail.eidolons.values())
                            ],
                            "_eidolon_index",
                        )
                    )
                case _:
                    msg = "Invalid page index"
                    raise ValueError(msg)

        if i.response.is_done():
            await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)

        self.message = await i.original_response()


class PageSelector(Select["CharacterUI"]):
    def __init__(self, current: int, hakushin: bool) -> None:
        if hakushin:
            options = [
                SelectOption(
                    label=LocaleStr(key="yatta_character_detail_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr(key="yatta_character_skill_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr(key="yatta_character_eidolon_page_label"),
                    value="2",
                    default=current == 2,
                ),
            ]
        else:
            options = [
                SelectOption(
                    label=LocaleStr(key="yatta_character_detail_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr(key="yatta_character_skill_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr(key="yatta_character_eidolon_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=LocaleStr(key="yatta_character_trace_page_label"),
                    value="3",
                    default=current == 3,
                ),
                SelectOption(
                    label=LocaleStr(key="character_stories_page_label"),
                    value="4",
                    default=current == 4,
                ),
                SelectOption(
                    label=LocaleStr(key="character_voices_page_label"),
                    value="5",
                    default=current == 5,
                ),
            ]
        super().__init__(options=options, row=4)

    async def callback(self, i: Interaction) -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select["CharacterUI"]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self._index_name = index_name

    async def callback(self, i: Interaction) -> Any:
        self.view.__setattr__(self._index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view.update(i)


class SkillLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="level_label"),
        is_digit=True,
        min_value=1,
    )

    def __init__(self, max_level: int) -> None:
        super().__init__(title=LocaleStr(key="skill_level.modal.title"))
        self.level.max_value = max_level


class EnterSkilLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr, skill_max_level: int) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)
        self._skill_max_level = skill_max_level

    async def callback(self, i: Interaction) -> Any:
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

        if isinstance(self.view._character_detail, yatta.CharacterDetail):
            async with YattaAPIClient(self.view.locale, self.view.translator) as api:
                self.view._main_skill_embeds[self.view._main_skill_index] = (
                    api.get_character_main_skill_embed(
                        self.view._character_detail.traces.main_skills[self.view._main_skill_index],
                        self.view._main_skill_levels[self.view._main_skill_index],
                    )
                )
        else:
            async with HakushinAPI(self.view.locale, self.view.translator) as api:
                self.view._main_skill_embeds[self.view._main_skill_index] = (
                    api.get_character_skill_embed(
                        list(self.view._character_detail.skills.values())[
                            self.view._main_skill_index
                        ],
                        self.view._main_skill_levels[self.view._main_skill_index],
                    )
                )

        await self.view.update(i)


class CharacterLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="level_label"),
        is_digit=True,
        min_value=1,
        max_value=80,
    )


class EnterCharacterLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> Any:
        modal = CharacterLevelModal(title=LocaleStr(key="chara_level.modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        incomplete = modal.incomplete
        if incomplete:
            return

        assert self.view._character_detail is not None
        assert self.view._manual_avatar is not None

        self.view._character_level = int(modal.level.value)

        if isinstance(self.view._character_detail, yatta.CharacterDetail):
            async with YattaAPIClient(self.view.locale, self.view.translator) as api:
                self.view._character_embed = api.get_character_details_embed(
                    self.view._character_detail,
                    self.view._character_level,
                    self.view._manual_avatar,
                )
        else:
            async with HakushinAPI(self.view.locale, self.view.translator) as api:
                self.view._character_embed = api.get_character_embed(
                    self.view._character_detail,
                    self.view._character_level,
                    self.view._convert_manual_avatar(self.view._manual_avatar),
                )

        await self.view.update(i)


class VoiceSelector(PaginatorSelect[CharacterUI]):
    async def callback(self, i: Interaction) -> Any:
        await super().callback()
        try:
            self.view._voice_index = int(self.values[0])
        except ValueError:
            await i.response.edit_message(view=self.view)
        else:
            await self.view.update(i)
