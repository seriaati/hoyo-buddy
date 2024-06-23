from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.hakushin import HakushinAPI
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View

if TYPE_CHECKING:
    from discord import Locale, Member, User
    from hakushin.models.hsr import LightConeDetail as HakushinLCDetail
    from yatta import LightConeDetail

    from hoyo_buddy.bot.bot import Interaction
    from hoyo_buddy.bot.translator import Translator


class LightConeUI(View):
    def __init__(
        self,
        light_cone_id: str,
        *,
        hakushin: bool,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._light_cone_id = light_cone_id
        self._light_cone_level = 80
        self._superimpose = 1
        self._lc_detail: LightConeDetail | HakushinLCDetail | None = None

        self._hakushin = hakushin

    @staticmethod
    def _convert_manual_avatar(manual_avatar: dict[str, dict[str, str]]) -> dict[str, str]:
        return {stat_id: stat["name"] for stat_id, stat in manual_avatar.items()}

    async def _fetch_embed(self) -> DefaultEmbed:
        if self._hakushin:
            async with YattaAPIClient(self.locale, self.translator) as api:
                manual_avatar = await api.fetch_manual_avatar()

            async with HakushinAPI(self.locale, self.translator) as api:
                try:
                    light_cone_id = int(self._light_cone_id)
                except ValueError:
                    raise InvalidQueryError from None

                lc_detail = await api.fetch_light_cone_detail(light_cone_id)
                self._lc_detail = lc_detail
                embed = api.get_light_cone_embed(
                    lc_detail,
                    self._light_cone_level,
                    self._superimpose,
                    self._convert_manual_avatar(manual_avatar),
                )
        else:
            async with YattaAPIClient(self.locale, self.translator) as api:
                try:
                    light_cone_id = int(self._light_cone_id)
                except ValueError:
                    raise InvalidQueryError from None

                lc_detail = await api.fetch_light_cone_detail(light_cone_id)
                self._lc_detail = lc_detail
                manual_avatar = await api.fetch_manual_avatar()
                embed = api.get_light_cone_embed(
                    lc_detail, self._light_cone_level, self._superimpose, manual_avatar
                )

        return embed

    def _setup_items(self) -> None:
        self.clear_items()
        self.add_item(
            EnterLightConeLevel(
                label=LocaleStr(key="enter_light_cone_level.button.label"),
            )
        )
        self.add_item(
            SuperimposeSelect(
                min_superimpose=1,
                max_superimpose=5,
                current_superimpose=self._superimpose,
            )
        )
        self.add_item(ShowStoryButton())

    async def start(self, i: Interaction) -> None:
        await i.response.defer()
        embed = await self._fetch_embed()
        self._setup_items()
        await i.edit_original_response(embed=embed, view=self)
        self.message = await i.original_response()


class LightConeLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="level_label"),
        placeholder="80",
        is_digit=True,
        min_value=1,
        max_value=80,
    )


class EnterLightConeLevel(Button[LightConeUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> Any:
        modal = LightConeLevelModal(title=LocaleStr(key="weapon_level.modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        incomplete = modal.incomplete
        if incomplete:
            return

        self.view._light_cone_level = int(modal.level.value)
        embed = await self.view._fetch_embed()
        self.view._setup_items()
        await i.edit_original_response(embed=embed, view=self.view)


class SuperimposeSelect(Select[LightConeUI]):
    def __init__(
        self, *, min_superimpose: int, max_superimpose: int, current_superimpose: int
    ) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(s=i, key="superimpose_indicator"),
                    value=str(i),
                    default=current_superimpose == i,
                )
                for i in range(min_superimpose, max_superimpose + 1)
            ]
        )

    async def callback(self, i: Interaction) -> Any:
        self.view._superimpose = int(self.values[0])
        embed = await self.view._fetch_embed()
        self.view._setup_items()
        await i.response.edit_message(embed=embed, view=self.view)


class ShowStoryButton(Button[LightConeUI]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="read_story.button.label"))

    async def callback(self, i: Interaction) -> Any:
        assert self.view._lc_detail is not None
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=self.view._lc_detail.name,
            description=self.view._lc_detail.description,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
