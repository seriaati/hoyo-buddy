from __future__ import annotations

from typing import TYPE_CHECKING, Any

import hakushin
from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.hakushin import HakushinAPI
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View

if TYPE_CHECKING:
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
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.character_id = character_id
        self.character_level = 90
        self.skill_index = 0
        self.passive_index = 0
        self.talent_level = 10
        self.const_index = 0
        self.selected_page = 0

    async def fetch_character_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            manual_weapon = await api.fetch_manual_weapon()

        async with HakushinAPI(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id, hakushin.Game.GI)
            return api.get_character_embed(
                character_detail, self.character_level, manual_weapon, hakushin.Game.GI
            )

    async def fetch_skill_embed(self) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterSkill]]:
        async with HakushinAPI(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id, hakushin.Game.GI)
            skill = character_detail.skills[self.skill_index]
            return (
                api.get_character_skill_embed(skill, self.talent_level),
                character_detail.skills,
            )

    async def fetch_passive_embed(self) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterPassive]]:
        async with HakushinAPI(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id, hakushin.Game.GI)
            passive = character_detail.passives[self.passive_index]
            return (api.get_character_passive_embed(passive), character_detail.passives)

    async def fetch_const_embed(
        self,
    ) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterConstellation]]:
        async with HakushinAPI(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id, hakushin.Game.GI)
            const = character_detail.constellations[self.const_index]
            return (api.get_character_const_embed(const), character_detail.constellations)

    async def update(self, i: INTERACTION) -> None:
        if not i.response.is_done():
            await i.response.defer()

        self.clear_items()
        self.add_item(PageSelector(self.selected_page))

        match self.selected_page:
            case 0:
                embed = await self.fetch_character_embed()
                self.add_item(
                    EnterCharacterLevel(
                        label=LocaleStr(
                            "Change character level", key="change_character_level_label"
                        )
                    )
                )
            case 1:
                embed, skills = await self.fetch_skill_embed()
                self.add_item(
                    EnterSkillLevel(
                        label=LocaleStr("Change skill level", key="change_skill_level_label")
                    )
                )
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=s.name,
                                value=str(i),
                                default=i == self.skill_index,
                            )
                            for i, s in enumerate(skills)
                        ],
                        "skill_index",
                    )
                )
            case 2:
                embed, passives = await self.fetch_passive_embed()
                self.add_item(
                    ItemSelector(
                        [
                            SelectOption(
                                label=p.name,
                                value=str(i),
                                default=i == self.passive_index,
                            )
                            for i, p in enumerate(passives)
                        ],
                        "passive_index",
                    )
                )
            case 3:
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
            case _:
                msg = f"Invalid page index: {self.selected_page}"
                raise ValueError(msg)

        await i.edit_original_response(embed=embed, view=self)
        self.message = await i.original_response()


class TalentLevelModal(Modal):
    level = TextInput(
        label=LocaleStr("Level", key="level_label"),
        placeholder="10",
        is_digit=True,
        min_value=1,
        max_value=10,
    )


class EnterSkillLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: INTERACTION) -> Any:
        modal = TalentLevelModal(
            title=LocaleStr("Enter Skill Level", key="skill_level.modal.title")
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        self.view.talent_level = int(modal.level.value)
        await self.view.update(i)


class CharacterLevelModal(Modal):
    level = TextInput(
        label=LocaleStr("Level", key="level_label"),
        placeholder="90",
        is_digit=True,
        min_value=1,
        max_value=90,
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

        self.view.character_level = int(modal.level.value)
        await self.view.update(i)


class PageSelector(Select[CharacterUI]):
    def __init__(self, current: int) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr("Profile", key="character_profile_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr("Skills", key="character_skills_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr("Passives", key="character_passives_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=LocaleStr("Constellations", key="character_const_page_label"),
                    value="3",
                    default=current == 3,
                ),
            ],
            row=4,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select[CharacterUI]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self.index_name = index_name

    async def callback(self, i: INTERACTION) -> Any:
        self.view.__setattr__(self.index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view.update(i)
