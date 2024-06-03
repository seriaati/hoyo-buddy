from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.hakushin import HakushinAPI
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


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
        self.superimpose = 1
        self._hakushin = hakushin

    async def _fetch_embed(self) -> DefaultEmbed:
        if self._hakushin:
            async with YattaAPIClient(self.locale, self.translator) as api:
                manual_avatar = await api.fetch_manual_avatar()

            async with HakushinAPI(self.locale, self.translator) as api:
                try:
                    light_cone_id = int(self._light_cone_id)
                except ValueError:
                    raise InvalidQueryError from None

                light_cone_detail = await api.fetch_light_cone_detail(light_cone_id)
                embed = api.get_light_cone_embed(
                    light_cone_detail, self._light_cone_level, self.superimpose, manual_avatar
                )
        else:
            async with YattaAPIClient(self.locale, self.translator) as api:
                try:
                    light_cone_id = int(self._light_cone_id)
                except ValueError:
                    raise InvalidQueryError from None

                light_cone_detail = await api.fetch_light_cone_detail(light_cone_id)
                manual_avatar = await api.fetch_manual_avatar()
                embed = api.get_light_cone_embed(
                    light_cone_detail, self._light_cone_level, self.superimpose, manual_avatar
                )

        return embed

    def _setup_items(self) -> None:
        self.clear_items()
        self.add_item(
            EnterLightConeLevel(
                label=LocaleStr(
                    "Change light cone level", key="enter_light_cone_level.button.label"
                ),
            )
        )
        self.add_item(
            Superposition(
                min_superposition=1,
                max_superposition=5,
                current_superposition=self.superimpose,
            )
        )

    async def start(self, i: INTERACTION) -> None:
        await i.response.defer()
        embed = await self._fetch_embed()
        self._setup_items()
        await i.edit_original_response(embed=embed, view=self)
        self.message = await i.original_response()


class LightConeLevelModal(Modal):
    level = TextInput(
        label=LocaleStr("Level", key="level_label"),
        placeholder="80",
        is_digit=True,
        min_value=1,
        max_value=80,
    )


class EnterLightConeLevel(Button[LightConeUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: INTERACTION) -> Any:
        modal = LightConeLevelModal(
            title=LocaleStr("Enter Weapon Level", key="weapon_level.modal.title")
        )
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


class Superposition(Select[LightConeUI]):
    def __init__(
        self, *, min_superposition: int, max_superposition: int, current_superposition: int
    ) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr("Superposition {s}", s=i, key="superposition_indicator"),
                    value=str(i),
                    default=current_superposition == i,
                )
                for i in range(min_superposition, max_superposition + 1)
            ]
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view.superimpose = int(self.values[0])
        embed = await self.view._fetch_embed()
        self.view._setup_items()
        await i.response.edit_message(embed=embed, view=self.view)
