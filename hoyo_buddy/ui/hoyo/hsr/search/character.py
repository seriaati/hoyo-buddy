from __future__ import annotations

from typing import TYPE_CHECKING, Any

import hakushin
import yatta
from discord import ButtonStyle

from hoyo_buddy.constants import HAKUSHIN_HSR_SKILL_TYPE_NAMES, locale_to_hakushin_lang
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Modal, PaginatorSelect, Select, SelectOption, TextInput, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from discord import Member, User

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction


class CharacterUI(View):
    def __init__(
        self, character_id: int, *, hakushin: bool, author: User | Member, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)

        self.selected_page = 0
        self._character_id = character_id
        self._character_level = 80

        self._main_skill_index = 0
        self._main_skill_max_levels: list[int] = []
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
        self._hakushin_translator = HakushinTranslator(self.locale)

    @staticmethod
    def _convert_manual_avatar(manual_avatar: dict[str, dict[str, str]]) -> dict[str, str]:
        return {stat_id: stat["name"] for stat_id, stat in manual_avatar.items()}

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        if self._hakushin:
            async with YattaAPIClient(self.locale) as api:
                manual_avatar = await api.fetch_manual_avatar()

            async with hakushin.HakushinAPI(
                hakushin.Game.HSR, locale_to_hakushin_lang(self.locale)
            ) as api:
                character_detail = await api.fetch_character_detail(self._character_id)

            self._character_detail = character_detail
            self._manual_avatar = manual_avatar

            self._main_skill_max_levels = self._main_skill_levels = [
                skill.max_level for skill in character_detail.skills.values()
            ]

            self._character_embed = self._hakushin_translator.get_character_embed(
                character_detail, self._character_level, self._convert_manual_avatar(manual_avatar)
            )

            self._main_skill_embeds = [
                self._hakushin_translator.get_character_skill_embed(skill, skill.max_level)
                for skill in character_detail.skills.values()
            ]
            self._eidolon_embeds = [
                self._hakushin_translator.get_character_eidolon_embed(eidolon)
                for eidolon in character_detail.eidolons.values()
            ]
        else:
            async with YattaAPIClient(self.locale) as api:
                character_detail = await api.fetch_character_detail(self._character_id)
                manual_avatar = await api.fetch_manual_avatar()

                self._character_detail = character_detail
                self._manual_avatar = manual_avatar

                self._main_skill_max_levels = self._main_skill_levels = [
                    sk.max_level
                    for skill in character_detail.traces.main_skills
                    for sk in skill.skill_list
                ]

                self._character_embed = api.get_character_details_embed(
                    character_detail, self._character_level, manual_avatar
                )
                self._main_skill_embeds = [
                    api.get_character_main_skill_embed(sk, skill.max_level)
                    for skill in character_detail.traces.main_skills
                    for sk in skill.skill_list
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

    def _build_yatta_ui_embed(self) -> DefaultEmbed | None:
        assert isinstance(self._character_detail, yatta.CharacterDetail)

        match self.selected_page:
            case 0:
                embed = self._character_embed
                self.add_item(EnterCharacterLevel(LocaleStr(key="change_character_level_label")))
            case 1:
                embed = self._main_skill_embeds[self._main_skill_index]
                self.add_item(
                    EnterSkilLevel(
                        label=LocaleStr(key="change_skill_level_label"),
                        skill_max_level=self._main_skill_max_levels[self._main_skill_index],
                    )
                )
                options: list[SelectOption] = []
                index = 0
                for skill in self._character_detail.traces.main_skills:
                    for sk in skill.skill_list:
                        options.append(
                            SelectOption(
                                label=f"{sk.type}: {sk.name}",
                                value=str(index),
                                default=index == self._main_skill_index,
                            )
                        )
                        index += 1
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
                                label=f"{s.name}",
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
                                label=s.title, value=str(index), default=index == self._story_index
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
                                label=v.title, value=str(index), default=index == self._voice_index
                            )
                            for index, v in enumerate(self._character_detail.script.voices)
                        ]
                    )
                )
            case _:
                msg = "Invalid page index"
                raise ValueError(msg)

        return embed

    def _build_hakushin_ui_embed(self) -> DefaultEmbed | None:
        assert isinstance(self._character_detail, hakushin.hsr.CharacterDetail)

        match self.selected_page:
            case 0:
                embed = self._character_embed
                self.add_item(EnterCharacterLevel(LocaleStr(key="change_character_level_label")))
            case 1:
                embed = self._main_skill_embeds[self._main_skill_index]
                self.add_item(
                    EnterSkilLevel(
                        label=LocaleStr(key="change_skill_level_label"),
                        skill_max_level=self._main_skill_max_levels[self._main_skill_index],
                    )
                )

                options: list[SelectOption] = []
                skills = list(self._character_detail.skills.values())
                for index, skill in enumerate(skills):
                    type_str_key = HAKUSHIN_HSR_SKILL_TYPE_NAMES.get(skill.type or "Talent")
                    type_str = LocaleStr(key=type_str_key).translate(self.locale)
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

        return embed

    def _generate_options(self) -> list[SelectOption]:
        options: list[SelectOption] = []

        if self._hakushin:
            options.extend(
                [
                    SelectOption(
                        label=LocaleStr(key="yatta_character_detail_page_label"),
                        value="0",
                        default=self.selected_page == 0,
                    ),
                    SelectOption(
                        label=LocaleStr(key="search.agent_page.skills"),
                        value="1",
                        default=self.selected_page == 1,
                    ),
                    SelectOption(
                        label=LocaleStr(key="yatta_character_eidolon_page_label"),
                        value="2",
                        default=self.selected_page == 2,
                    ),
                ]
            )
        else:
            options.append(
                SelectOption(
                    label=LocaleStr(key="yatta_character_detail_page_label"),
                    value="0",
                    default=self.selected_page == 0,
                )
            )
            if self._main_skill_embeds:
                options.append(
                    SelectOption(
                        label=LocaleStr(key="search.agent_page.skills"),
                        value="1",
                        default=self.selected_page == 1,
                    )
                )
            if self._eidolon_embeds:
                options.append(
                    SelectOption(
                        label=LocaleStr(key="yatta_character_eidolon_page_label"),
                        value="2",
                        default=self.selected_page == 2,
                    )
                )
            if self._sub_skill_embeds:
                options.append(
                    SelectOption(
                        label=LocaleStr(key="yatta_character_trace_page_label"),
                        value="3",
                        default=self.selected_page == 3,
                    )
                )
            if self._story_embeds:
                options.append(
                    SelectOption(
                        label=LocaleStr(key="character_stories_page_label"),
                        value="4",
                        default=self.selected_page == 4,
                    )
                )
            if self._voice_embeds:
                options.append(
                    SelectOption(
                        label=LocaleStr(key="character_voices_page_label"),
                        value="5",
                        default=self.selected_page == 5,
                    )
                )

        return options

    async def update(self, i: Interaction) -> None:
        if self._character_detail is None:
            msg = "Character detail not fetched"
            raise RuntimeError(msg)

        self.clear_items()
        options = self._generate_options()
        self.add_item(PageSelector(options))

        if isinstance(self._character_detail, yatta.CharacterDetail):
            embed = self._build_yatta_ui_embed()
        else:
            embed = self._build_hakushin_ui_embed()

        if i.response.is_done():
            self.message = await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)
            self.message = await i.original_response()


class PageSelector(Select["CharacterUI"]):
    def __init__(self, options: list[SelectOption]) -> None:
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
    level = TextInput(label=LocaleStr(key="characters.sorter.level"), is_digit=True, min_value=1)

    def __init__(self, max_level: int) -> None:
        super().__init__(title=LocaleStr(key="skill_level.modal.title"))
        self.level.max_value = max_level


class EnterSkilLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr, skill_max_level: int) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)
        self._skill_max_level = skill_max_level

    async def callback(self, i: Interaction) -> Any:
        modal = SkillLevelModal(self._skill_max_level)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        assert self.view._character_detail is not None
        assert self.view._main_skill_index is not None

        self.view._main_skill_levels[self.view._main_skill_index] = int(modal.level.value)

        if isinstance(self.view._character_detail, yatta.CharacterDetail):
            async with YattaAPIClient(self.view.locale) as api:
                skills = [
                    sk
                    for skill in self.view._character_detail.traces.main_skills
                    for sk in skill.skill_list
                ]
                self.view._main_skill_embeds[self.view._main_skill_index] = (
                    api.get_character_main_skill_embed(
                        skills[self.view._main_skill_index],
                        self.view._main_skill_levels[self.view._main_skill_index],
                    )
                )
        else:
            self.view._main_skill_embeds[self.view._main_skill_index] = (
                self.view._hakushin_translator.get_character_skill_embed(
                    list(self.view._character_detail.skills.values())[self.view._main_skill_index],
                    self.view._main_skill_levels[self.view._main_skill_index],
                )
            )

        await self.view.update(i)


class CharacterLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="characters.sorter.level"), is_digit=True, min_value=1, max_value=80
    )


class EnterCharacterLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> Any:
        modal = CharacterLevelModal(title=LocaleStr(key="chara_level.modal.title"))
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        assert self.view._character_detail is not None
        assert self.view._manual_avatar is not None

        self.view._character_level = int(modal.level.value)

        if isinstance(self.view._character_detail, yatta.CharacterDetail):
            async with YattaAPIClient(self.view.locale) as api:
                self.view._character_embed = api.get_character_details_embed(
                    self.view._character_detail,
                    self.view._character_level,
                    self.view._manual_avatar,
                )
        else:
            self.view._character_embed = self.view._hakushin_translator.get_character_embed(
                self.view._character_detail,
                self.view._character_level,
                self.view._convert_manual_avatar(self.view._manual_avatar),
            )

        await self.view.update(i)


class VoiceSelector(PaginatorSelect[CharacterUI]):
    async def callback(self, i: Interaction) -> Any:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view._voice_index = int(self.values[0])
        await self.view.update(i)
        return None
