from typing import TYPE_CHECKING, Any

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.genshin.ambr import AmbrAPIClient
from hoyo_buddy.ui import LevelModalButton, Select, SelectOption, View

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.embeds import DefaultEmbed


class WeaponUI(View):
    def __init__(
        self,
        weapon_id: str,
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.weapon_id = weapon_id
        self.weapon_level = 90
        self.refinement = 1
        self.max_refinement = 1

    async def _fetch_weapon_embed(self) -> "DefaultEmbed":
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

    def _setup_items(self) -> None:
        self.clear_items()
        self.add_item(
            WeaponLevelModalButton(
                True,
                min_level=1,
                max_level=90,
                default_level=self.weapon_level,
                label=LocaleStr("Change weapon level", key="change_weapon_level_label"),
            )
        )
        self.add_item(
            RefinementSelector(
                min_refinement=1,
                max_refinement=self.max_refinement,
                current_refinement=self.refinement,
            )
        )

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()
        embed = await self._fetch_weapon_embed()
        self._setup_items()
        await i.edit_original_response(embed=embed, view=self)


class WeaponLevelModalButton(LevelModalButton["WeaponUI"]):
    def __init__(
        self,
        is_character_level: bool,
        *,
        min_level: int,
        max_level: int,
        default_level: int | None = None,
        label: LocaleStr,
    ) -> None:
        super().__init__(
            min_level=min_level, max_level=max_level, default_level=default_level, label=label
        )
        self.is_character_level = is_character_level

    async def callback(self, i: "INTERACTION") -> Any:
        await super().callback(i)
        self.view.weapon_level = self.level
        embed = await self.view._fetch_weapon_embed()
        self.view._setup_items()
        await i.edit_original_response(embed=embed, view=self.view)


class RefinementSelector(Select["WeaponUI"]):
    def __init__(
        self, *, min_refinement: int, max_refinement: int, current_refinement: int
    ) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr("Refinement {r}", r=i, key="refinement_indicator"),
                    value=str(i),
                    default=current_refinement == i,
                )
                for i in range(min_refinement, max_refinement + 1)
            ]
        )

    async def callback(self, i: "INTERACTION") -> Any:
        self.view.refinement = int(self.values[0])
        embed = await self.view._fetch_weapon_embed()
        self.view._setup_items()
        await i.response.edit_message(embed=embed, view=self.view)
