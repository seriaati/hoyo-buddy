from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

import hakushin

from hoyo_buddy.constants import locale_to_hakushin_lang
from hoyo_buddy.emojis import ZZZ_SKILL_TYPE_CORE, ZZZ_SKILL_TYPE_EMOJIS
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Select, SelectOption, View
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

    from hoyo_buddy.types import Interaction, User

__all__ = ("AgentSearchView",)

SKILL_TYPE_LOCALE_STRS: Final[dict[hakushin.enums.ZZZSkillType, LocaleStr]] = {
    hakushin.enums.ZZZSkillType.ASSIST: LocaleStr(key="zzz.assist"),
    hakushin.enums.ZZZSkillType.BASIC: LocaleStr(key="zzz.basic"),
    hakushin.enums.ZZZSkillType.CHAIN: LocaleStr(key="zzz.chain"),
    hakushin.enums.ZZZSkillType.DODGE: LocaleStr(key="zzz.dodge"),
    hakushin.enums.ZZZSkillType.SPECIAL: LocaleStr(key="zzz.special"),
}


class AgentSearchView(View):
    def __init__(self, agent_id: int, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self._agent_id = agent_id
        self._agent: hakushin.zzz.CharacterDetail
        self._page: Literal["info", "skills", "cinemas", "core"] = "info"
        self._cinema_index: int = 0
        self._skill_type: hakushin.enums.ZZZSkillType = hakushin.enums.ZZZSkillType.BASIC
        self._hakushin_translator = HakushinTranslator(locale)

    def _add_items(self) -> None:
        self.add_item(PageSelect(self._page))

    def _update_items(self) -> None:
        self.clear_items()
        if self._page in {"skills", "core"}:
            self.add_item(SkillSelect(list(self._agent.skills.keys()), self._skill_type, self._page))
        elif self._page == "cinemas":
            self.add_item(CinemaSelect(self._agent.mindscape_cinemas, self._cinema_index))
        self.add_item(PageSelect(self._page))

    async def _fetch_data(self) -> None:
        async with hakushin.HakushinAPI(hakushin.Game.ZZZ, locale_to_hakushin_lang(self.locale)) as api:
            self._agent = await api.fetch_character_detail(self._agent_id)

    async def update(self, i: Interaction) -> None:
        self._update_items()

        if self._page == "info":
            embed = self._hakushin_translator.get_agent_info_embed(self._agent)
        elif self._page == "skills":
            skill = self._agent.skills[self._skill_type]
            embed = self._hakushin_translator.get_agent_skill_embed(skill, self._agent)
        elif self._page == "core":
            skill = self._agent.passive
            embed = self._hakushin_translator.get_agent_core_embed(skill, self._agent)
        else:
            cinema = self._agent.mindscape_cinemas[self._cinema_index]
            embed = self._hakushin_translator.get_agent_cinema_embed(
                cinema, self._agent.id, self._cinema_index, self._agent
            )

        if i.response.is_done():
            await i.edit_original_response(embed=embed, view=self)
        else:
            await i.response.edit_message(embed=embed, view=self)

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        await self._fetch_data()
        self._add_items()
        await self.update(i)
        self.message = await i.original_response()


class PageSelect(Select[AgentSearchView]):
    def __init__(self, current: str) -> None:
        keys = ("info", "skills", "cinemas")
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(key=f"search.agent_page.{key}"),
                    value=key,
                    default=current == key or (current == "core" and key == "skills"),
                )
                for key in keys
            ],
            placeholder=LocaleStr(key="search.agent_page.placeholder"),
        )

    async def callback(self, i: Interaction) -> None:
        self.view._page = self.values[0]  # pyright: ignore[reportAttributeAccessIssue]
        await self.view.update(i)


class SkillSelect(Select[AgentSearchView]):
    def __init__(
        self, skill_types: Sequence[hakushin.enums.ZZZSkillType], current: hakushin.enums.ZZZSkillType, page: str
    ) -> None:
        options = [
            SelectOption(
                label=SKILL_TYPE_LOCALE_STRS[skill_type],
                value=skill_type.value,
                emoji=ZZZ_SKILL_TYPE_EMOJIS[skill_type],
                default=skill_type == current and page != "core",
            )
            for skill_type in skill_types
        ]
        options.append(
            SelectOption(
                label=LocaleStr(key="zzz.core"), value="core", emoji=ZZZ_SKILL_TYPE_CORE, default=page == "core"
            )
        )
        super().__init__(options=options, placeholder=LocaleStr(key="zzz.skill_type.placeholder"))

    async def callback(self, i: Interaction) -> None:
        if self.values[0] == "core":
            self.view._page = "core"
        else:
            self.view._page = "skills"
            self.view._skill_type = hakushin.enums.ZZZSkillType(self.values[0])
        await self.view.update(i)


class CinemaSelect(Select[AgentSearchView]):
    def __init__(self, cinemas: Sequence[hakushin.zzz.MindscapeCinema], current: int) -> None:
        options = [
            SelectOption(label=f"{i + 1}. {cinema.name}", value=str(i), default=i == current)
            for i, cinema in enumerate(cinemas)
        ]
        super().__init__(options=options, placeholder=LocaleStr(key="zzz.cinema.placeholder"))

    async def callback(self, i: Interaction) -> None:
        self.view._cinema_index = int(self.values[0])
        await self.view.update(i)
