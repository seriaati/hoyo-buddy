from __future__ import annotations

from typing import TYPE_CHECKING, Any

import hakushin
from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.clients.hakushin import HakushinTranslator
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, View
from hoyo_buddy.utils import ephemeral

from .....constants import LOCALE_TO_HAKUSHIN_LANG

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction


class WeaponUI(View):
    def __init__(
        self,
        weapon_id: str,
        *,
        hakushin: bool,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.weapon_id = weapon_id
        self.weapon_level = 90
        self.refinement = 1
        self.max_refinement = 1
        self.hakushin = hakushin

    async def _fetch_weapon_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            try:
                weapon_id = int(self.weapon_id)
            except ValueError:
                raise InvalidQueryError from None

            weapon_detail = await api.fetch_weapon_detail(weapon_id)
            weapon_curve = await api.fetch_weapon_curve()
            manual_weapon = await api.fetch_manual_weapon()
            embed = api.get_weapon_embed(
                weapon_detail,
                self.weapon_level,
                self.refinement,
                weapon_curve,
                manual_weapon,
            )
            self.max_refinement = len(weapon_detail.upgrade.awaken_cost) + 1

            return embed

    async def _fetch_hakushin_weapon_embed(self) -> DefaultEmbed:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            manual_weapon = await api.fetch_manual_weapon()

        async with hakushin.HakushinAPI(
            hakushin.Game.GI, LOCALE_TO_HAKUSHIN_LANG[self.locale]
        ) as api:
            try:
                weapon_id = int(self.weapon_id)
            except ValueError:
                raise InvalidQueryError from None

            weapon_detail = await api.fetch_weapon_detail(weapon_id)

        translator = HakushinTranslator(self.locale, self.translator)
        embed = translator.get_weapon_embed(
            weapon_detail,
            self.weapon_level,
            self.refinement,
            manual_weapon,
        )
        self.max_refinement = len(weapon_detail.refinments)

        return embed

    async def _get_embed(self) -> DefaultEmbed:
        if self.hakushin:
            return await self._fetch_hakushin_weapon_embed()
        return await self._fetch_weapon_embed()

    def _setup_items(self) -> None:
        self.clear_items()
        self.add_item(EnterWeaponLevel(label=LocaleStr(key="change_weapon_level_label")))
        self.add_item(
            RefinementSelector(
                min_refinement=1,
                max_refinement=self.max_refinement,
                current_refinement=self.refinement,
            )
        )

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        embed = await self._get_embed()
        self._setup_items()
        await i.edit_original_response(embed=embed, view=self)
        self.message = await i.original_response()


class WeaponLevelModal(Modal):
    level = TextInput(
        label=LocaleStr(key="level_label"),
        placeholder="90",
        is_digit=True,
        min_value=1,
        max_value=90,
    )


class EnterWeaponLevel(Button[WeaponUI]):
    def __init__(self, label: LocaleStr) -> None:
        super().__init__(label=label, style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> Any:
        modal = WeaponLevelModal(title=LocaleStr(key="weapon_level.modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        incomplete = modal.incomplete
        if incomplete:
            return

        self.view.weapon_level = int(modal.level.value)
        embed = await self.view._get_embed()
        self.view._setup_items()
        await i.edit_original_response(embed=embed, view=self.view)


class RefinementSelector(Select["WeaponUI"]):
    def __init__(
        self, *, min_refinement: int, max_refinement: int, current_refinement: int
    ) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(r=i, key="refinement_indicator"),
                    value=str(i),
                    default=current_refinement == i,
                )
                for i in range(min_refinement, max_refinement + 1)
            ]
        )

    async def callback(self, i: Interaction) -> Any:
        self.view.refinement = int(self.values[0])
        embed = await self.view._get_embed()
        self.view._setup_items()
        await i.response.edit_message(embed=embed, view=self.view)
