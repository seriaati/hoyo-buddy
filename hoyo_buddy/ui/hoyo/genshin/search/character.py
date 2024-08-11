from __future__ import annotations

from typing import TYPE_CHECKING, Any

import hakushin
from discord import ButtonStyle, Locale, Member, User

from hoyo_buddy.constants import GI_SKILL_TYPE_KEYS, locale_to_hakushin_lang
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Modal, PaginatorSelect, Select, SelectOption, TextInput, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    import ambr

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction


class CharacterUI(View):
    def __init__(
        self,
        character_id: str,
        *,
        hakushin: bool,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.character_id = character_id
        self.character_level = 90
        self.talent_index = 0
        self.talent_level = 10
        self.const_index = 0
        self.story_index = 0
        self.quote_index = 0
        self.selected_page = 8 if hakushin else 0

        # hakushin specific
        self.hakushin = hakushin
        self.skill_index = 0
        self.passive_index = 0
        self._hakushin_translator = HakushinTranslator(self.locale, self.translator)

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

    async def fetch_talent_embed(self) -> tuple[DefaultEmbed, bool, list[ambr.Talent]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            talent = character_detail.talents[self.talent_index]
            talent_max_level = self.talent_level if talent.upgrades else 0
            return (
                api.get_character_talent_embed(talent, talent_max_level),
                bool(talent.upgrades),
                character_detail.talents,
            )

    async def fetch_const_embed(self) -> tuple[DefaultEmbed, list[ambr.Constellation]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            const = character_detail.constellations[self.const_index]
            return (
                api.get_character_constellation_embed(const),
                character_detail.constellations,
            )

    async def fetch_story_embed(self) -> tuple[DefaultEmbed, list[ambr.Story]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            story = character_fetter.stories[self.story_index]
            return (
                api.get_character_story_embed(story),
                character_fetter.stories,
            )

    async def fetch_quote_embed(self) -> tuple[DefaultEmbed, list[ambr.Quote]]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            character_fetter = await api.fetch_character_fetter(self.character_id)
            quote = character_fetter.quotes[self.quote_index]
            return (
                api.get_character_quote_embed(quote, self.character_id),
                character_fetter.quotes,
            )

    async def fetch_hakushin_character_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            manual_weapon = await api.fetch_manual_weapon()

        async with hakushin.HakushinAPI(
            hakushin.Game.GI, locale_to_hakushin_lang(self.locale)
        ) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
        return self._hakushin_translator.get_character_embed(
            character_detail, self.character_level, manual_weapon
        )

    async def fetch_hakushin_skill_embed(
        self,
    ) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterSkill]]:
        async with hakushin.HakushinAPI(
            hakushin.Game.GI, locale_to_hakushin_lang(self.locale)
        ) as api:
            character_detail = await api.fetch_character_detail(self.character_id)

        skill = character_detail.skills[self.skill_index]
        return (
            self._hakushin_translator.get_character_skill_embed(skill, self.talent_level),
            character_detail.skills,
        )

    async def fetch_hakushin_passive_embed(
        self,
    ) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterPassive]]:
        async with hakushin.HakushinAPI(
            hakushin.Game.GI, locale_to_hakushin_lang(self.locale)
        ) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            passive = character_detail.passives[self.passive_index]
        return (
            self._hakushin_translator.get_character_passive_embed(passive),
            character_detail.passives,
        )

    async def fetch_hakushin_const_embed(
        self,
    ) -> tuple[DefaultEmbed, list[hakushin.gi.CharacterConstellation]]:
        async with hakushin.HakushinAPI(
            hakushin.Game.GI, locale_to_hakushin_lang(self.locale)
        ) as api:
            character_detail = await api.fetch_character_detail(self.character_id)
            const = character_detail.constellations[self.const_index]

        return (
            self._hakushin_translator.get_character_const_embed(const),
            character_detail.constellations,
        )

    async def update(self, i: Interaction) -> None:  # noqa: PLR0912, PLR0915
        if not i.response.is_done():
            await i.response.defer(ephemeral=ephemeral(i))

        self.clear_items()
        self.add_item(PageSelector(self.selected_page, self.hakushin))

        match self.selected_page:
            case 0:
                embed = await self.fetch_character_embed()
                self.add_item(
                    EnterCharacterLevel(
                        label=LocaleStr(key="change_character_characters.sorter.level")
                    )
                )
            case 1:
                embed, upgradeable, talents = await self.fetch_talent_embed()
                if upgradeable:
                    self.add_item(
                        EnterTalentLevel(
                            label=LocaleStr(key="change_talent_characters.sorter.level")
                        )
                    )

                options: list[SelectOption] = []
                for index, talent in enumerate(talents):
                    skill_type_key = GI_SKILL_TYPE_KEYS.get(index)
                    label_prefix = (
                        LocaleStr(key=skill_type_key) if skill_type_key is not None else None
                    )
                    label = (
                        f"{label_prefix.translate(self.translator, self.locale)}: {talent.name}"
                        if label_prefix is not None
                        else talent.name
                    )
                    options.append(
                        SelectOption(
                            label=label,
                            value=str(index),
                            default=index == self.talent_index,
                        )
                    )
                self.add_item(ItemSelector(options, "talent_index"))
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
            case 5:
                embed, skills = await self.fetch_hakushin_skill_embed()
                self.add_item(
                    EnterTalentLevel(label=LocaleStr(key="change_skill_characters.sorter.level"))
                )

                options: list[SelectOption] = []
                for index, skill in enumerate(skills):
                    skill_type_key = GI_SKILL_TYPE_KEYS.get(index)
                    label_prefix = (
                        LocaleStr(key=skill_type_key) if skill_type_key is not None else None
                    )
                    label = (
                        f"{label_prefix.translate(self.translator, self.locale)}: {skill.name}"
                        if label_prefix is not None
                        else skill.name
                    )
                    options.append(
                        SelectOption(
                            label=label, value=str(index), default=index == self.skill_index
                        )
                    )
                self.add_item(ItemSelector(options, "skill_index"))
            case 6:
                embed, passives = await self.fetch_hakushin_passive_embed()
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
            case 7:
                embed, consts = await self.fetch_hakushin_const_embed()
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
            case 8:
                embed = await self.fetch_hakushin_character_embed()
                self.add_item(
                    EnterCharacterLevel(
                        label=LocaleStr(key="change_character_characters.sorter.level")
                    )
                )
            case _:
                msg = f"Invalid page index: {self.selected_page}"
                raise ValueError(msg)

        await i.edit_original_response(embed=embed, view=self)
        self.message = await i.original_response()


class TalentLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="characters.sorter.level"),
        placeholder="10",
        is_digit=True,
        min_value=1,
        max_value=10,
    )


class EnterTalentLevel(Button[CharacterUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> Any:
        modal = TalentLevelModal(title=LocaleStr(key="talent_level.modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        self.view.talent_level = int(modal.level.value)
        await self.view.update(i)


class CharacterLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="characters.sorter.level"),
        placeholder="90",
        is_digit=True,
        min_value=1,
        max_value=90,
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

        self.view.character_level = int(modal.level.value)
        await self.view.update(i)


class PageSelector(Select[CharacterUI]):
    def __init__(self, current: int, hakushin: bool) -> None:
        if hakushin:
            options = [
                SelectOption(
                    label=LocaleStr(key="character_profile_page_label"),
                    value="8",
                    default=current == 8,
                ),
                SelectOption(
                    label=LocaleStr(key="search.agent_page.skills"),
                    value="5",
                    default=current == 5,
                ),
                SelectOption(
                    label=LocaleStr(key="character_passives_page_label"),
                    value="6",
                    default=current == 6,
                ),
                SelectOption(
                    label=LocaleStr(key="character_const_page_label"),
                    value="7",
                    default=current == 7,
                ),
            ]
        else:
            options = [
                SelectOption(
                    label=LocaleStr(key="character_profile_page_label"),
                    value="0",
                    default=current == 0,
                ),
                SelectOption(
                    label=LocaleStr(key="character_talents_page_label"),
                    value="1",
                    default=current == 1,
                ),
                SelectOption(
                    label=LocaleStr(key="character_const_page_label"),
                    value="2",
                    default=current == 2,
                ),
                SelectOption(
                    label=LocaleStr(key="character_stories_page_label"),
                    value="3",
                    default=current == 3,
                ),
                SelectOption(
                    label=LocaleStr(key="character_quotes_page_label"),
                    value="4",
                    default=current == 4,
                ),
            ]
        super().__init__(options=options, row=4)

    async def callback(self, i: Interaction) -> Any:
        self.view.selected_page = int(self.values[0])
        await self.view.update(i)


class ItemSelector(Select[CharacterUI]):
    def __init__(self, options: list[SelectOption], index_name: str) -> None:
        super().__init__(options=options)
        self.index_name = index_name

    async def callback(self, i: Interaction) -> Any:
        self.view.__setattr__(self.index_name, int(self.values[0]))  # noqa: PLC2801
        await self.view.update(i)


class QuoteSelector(PaginatorSelect[CharacterUI]):
    async def callback(self, i: Interaction) -> Any:
        await super().callback()
        try:
            self.view.quote_index = int(self.values[0])
        except ValueError:
            await i.response.edit_message(view=self.view)
        else:
            await self.view.update(i)
