from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import akasha

from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import Button
from hoyo_buddy.ui.paginator import Page, PaginatorView

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction, User


class AkashaLbPaginator(PaginatorView):
    def __init__(
        self,
        calculation_id: str,
        lb_embed: DefaultEmbed,
        you: akasha.Leaderboard | None,
        lb_size: int,
        lb_details: str,
        *,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__({}, author=author, locale=locale)
        self.add_item(ShowLbDetailsButton())

        self.calculation_id = calculation_id
        self.lb_embed = lb_embed
        self.lb_details = lb_details
        self.you = you
        self.lb_size = lb_size

        self.lbs: list[akasha.Leaderboard] = []
        self._max_page = math.ceil(lb_size / 10)

    def get_lb_line(self, lb: akasha.Leaderboard) -> str:
        profile_url = f"https://akasha.cv/profile/{lb.uid}"
        crit_rate = round(lb.stats[akasha.CharaStatType.CRIT_RATE].value * 100, 1)
        crit_dmg = round(lb.stats[akasha.CharaStatType.CRIT_DMG].value * 100, 1)
        crit_value = round(lb.crit_value, 1)
        damage = int(round(lb.calculation.result, 0))
        return f"{lb.rank}. [{lb.owner.nickname}]({profile_url}) - **{damage:,}** - {crit_value} CV ({crit_rate}/{crit_dmg})"

    def get_page_embed(self, lbs: list[akasha.Leaderboard]) -> DefaultEmbed:
        embed = self.lb_embed.copy()

        if self.you is not None:
            top_percent = LocaleStr(
                key="top_percent", percent=round(self.you.rank / self.lb_size * 100, 1)
            ).translate(self.locale)
            you_str = LocaleStr(key="akasha_you").translate(self.locale)

            embed.add_field(
                name=f"{you_str} ({top_percent})", value=self.get_lb_line(self.you), inline=False
            )

        return embed.add_field(
            name="---", value="\n".join(self.get_lb_line(lb) for lb in lbs), inline=False
        )

    async def fetch_page(self, type_: Literal["next", "prev", "first", "last", "start"]) -> Page:
        if type_ in {"first", "start"}:
            p = ""
        elif type_ == "last":
            p = "gt|-100000000"
        elif type_ == "prev":
            p = f"gt|{self.lbs[0].calculation.result}"
        else:
            p = f"lt|{self.lbs[-1].calculation.result}"

        async with akasha.AkashaAPI() as api:
            self.lbs = await api._fetch_leaderboards(
                int(self.calculation_id), self._current_page + 1, 10, p, True
            )

        return Page(embed=self.get_page_embed(self.lbs))

    async def _update_page(
        self,
        i: Interaction,
        *,
        type_: Literal["next", "prev", "first", "last", "start"],
        followup: bool = False,
        ephemeral: bool = False,
    ) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=ephemeral)

        self._pages[self._current_page] = await self.fetch_page(type_)
        return await super()._update_page(i, type_=type_, followup=followup, ephemeral=ephemeral)


class ShowLbDetailsButton(Button[AkashaLbPaginator]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="akasha_show_details"), row=1)

    async def callback(self, i: Interaction) -> None:
        await i.response.send_message(self.view.lb_details, ephemeral=True)
