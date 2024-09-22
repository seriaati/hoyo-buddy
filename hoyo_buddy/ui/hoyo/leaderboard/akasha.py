from __future__ import annotations

from typing import TYPE_CHECKING

import akasha

from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.ui.paginator import Page, PaginatorView

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction, User


class LeaderboardPaginator(PaginatorView):
    def __init__(
        self,
        calculation_id: str,
        lb_embed: DefaultEmbed,
        total_page: int,
        *,
        author: User,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__([], author=author, locale=locale, translator=translator)

        self.calculation_id = calculation_id
        self.lb_embed = lb_embed
        self.lbs: list[akasha.Leaderboard] = []

        self._max_page = total_page

    def get_lb_line(self, lb: akasha.Leaderboard) -> str:
        profile_url = f"https://akasha.cv/profile/{lb.uid}"
        crit_rate = lb.stats[akasha.CharaStatType.CRIT_RATE]
        crit_dmg = lb.stats[akasha.CharaStatType.CRIT_DMG]
        crit_value = round(lb.crit_value, 1)
        damage = round(lb.calculation.result, 1)
        return f"{lb.rank}. [{lb.owner.nickname}]({profile_url}) - {crit_rate}:{crit_dmg} {crit_value} cv {damage}"

    def get_page_embed(self, lbs: list[akasha.Leaderboard]) -> DefaultEmbed:
        embed = self.lb_embed.copy()
        embed.add_field(
            name=LocaleStr(key="akasha_entries"),
            value="\n".join(self.get_lb_line(lb) for lb in lbs),
        )
        return embed

    async def fetch_page(self) -> Page:
        async with akasha.AkashaAPI() as api:
            self.lbs = await api._fetch_leaderboards(
                int(self.calculation_id),
                self._current_page + 1,
                10,
                f"lt|{self.lbs[-1].calculation.result}" if self.lbs else "",
                True,
            )

        return Page(embed=self.get_page_embed(self.lbs))

    async def _update_page(
        self, i: Interaction, *, followup: bool = False, ephemeral: bool = False
    ) -> None:
        self._pages[self._current_page] = await self.fetch_page()
        return await super()._update_page(i, followup=followup, ephemeral=ephemeral)
