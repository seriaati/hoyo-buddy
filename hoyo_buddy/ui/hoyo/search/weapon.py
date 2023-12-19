import contextlib
from typing import Any, Optional, Tuple, Union

from discord import InteractionResponded, Locale, Member, User

from ....bot import INTERACTION, Translator
from ....bot.translator import locale_str as _T
from ....embeds import DefaultEmbed
from ....exceptions import InvalidQuery
from ....hoyo.genshin.ambr import AmbrAPIClient
from ...ui import LevelModalButton as LMB
from ...ui import Select, SelectOption, View


class WeaponUI(View):
    def __init__(
        self,
        weapon_id: str,
        *,
        author: Union[User, Member],
        locale: Locale,
        translator: Translator,
    ):
        super().__init__(author=author, locale=locale, translator=translator)
        self.weapon_id = weapon_id
        self.weapon_level = 90
        self.refinement = 1

    async def fetch_weapon_embed(self) -> Tuple[DefaultEmbed, int]:
        async with AmbrAPIClient(self.locale, self.translator) as api:
            try:
                weapon_id = int(self.weapon_id)
            except ValueError:
                raise InvalidQuery from None

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
            return embed, len(weapon_detail.upgrade.awaken_cost) + 1

    async def update(self, i: INTERACTION) -> None:
        with contextlib.suppress(InteractionResponded):
            await i.response.defer()

        embed, max_refinement = await self.fetch_weapon_embed()

        self.clear_items()
        self.add_item(
            LevelModalButton(
                True,
                min_level=1,
                max_level=90,
                default_level=self.weapon_level,
                label=_T("Change weapon level", key="change_weapon_level_label"),
            )
        )
        self.add_item(
            RefinementSelector(
                min_refinement=1,
                max_refinement=max_refinement,
                current_refinement=self.refinement,
            )
        )
        await i.edit_original_response(embed=embed, view=self)


class LevelModalButton(LMB):
    def __init__(
        self,
        is_character_level: bool,
        *,
        min_level: int,
        max_level: int,
        default_level: Optional[int] = None,
        label: _T,
    ):
        super().__init__(
            min_level=min_level, max_level=max_level, default_level=default_level, label=label
        )
        self.is_character_level = is_character_level

    async def callback(self, i: INTERACTION) -> Any:
        self.view: WeaponUI
        await super().callback(i)
        self.view.weapon_level = self.level
        await self.view.update(i)


class RefinementSelector(Select):
    def __init__(self, *, min_refinement: int, max_refinement: int, current_refinement: int):
        super().__init__(
            options=[
                SelectOption(
                    label=_T("Refinement {r}", r=i, key="refinement_indicator"),
                    value=str(i),
                    default=current_refinement == i,
                )
                for i in range(min_refinement, max_refinement + 1)
            ]
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: WeaponUI
        self.view.refinement = int(self.values[0])
        await self.view.update(i)
