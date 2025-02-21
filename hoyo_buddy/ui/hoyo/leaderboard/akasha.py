from __future__ import annotations

import itertools
import math
from typing import TYPE_CHECKING, Literal

import akasha

from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button
from hoyo_buddy.ui.paginator import Page, PaginatorView

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.types import Interaction, User


class BaseAkashaLbPaginator(PaginatorView):
    def __init__(
        self,
        lb_embed: DefaultEmbed,
        you: akasha.Leaderboard | None,
        lb_size: int,
        real_lb_size: int,
        *,
        lbs: list[akasha.Leaderboard] | None = None,
        author: User,
        locale: Locale,
    ) -> None:
        self.lb_embed = lb_embed
        self.you = you
        self.lb_size = lb_size
        self.real_lb_size = real_lb_size
        self.locale = locale

        super().__init__(
            {
                i: Page(embed=self.get_page_embed(chunked_lbs))
                for i, chunked_lbs in enumerate(itertools.batched(lbs or [], 10))
            },
            author=author,
            locale=locale,
        )
        self._max_page = math.ceil(lb_size / 10)

    @staticmethod
    def get_lb_line(lb: akasha.Leaderboard) -> str:
        profile_url = f"https://akasha.cv/profile/{lb.uid}"
        crit_rate = round(lb.stats[akasha.CharaStatType.CRIT_RATE].value * 100, 1)
        crit_dmg = round(lb.stats[akasha.CharaStatType.CRIT_DMG].value * 100, 1)
        crit_value = round(lb.crit_value, 1)
        damage = int(round(lb.calculation.result, 0))
        return f"`{lb.rank}.` [{lb.owner.nickname}]({profile_url}) - **{damage:,}** - {crit_value} CV ({crit_rate}/{crit_dmg})"

    def get_page_embed(self, lbs: Sequence[akasha.Leaderboard]) -> DefaultEmbed:
        embed = self.lb_embed.copy()

        if self.you is not None:
            top_percent = LocaleStr(
                key="top_percent", percent=round(self.you.rank / self.real_lb_size * 100, 1)
            ).translate(self.locale)
            you_str = LocaleStr(key="akasha_you").translate(self.locale)

            embed.add_field(
                name=f"{you_str} ({top_percent})", value=self.get_lb_line(self.you), inline=False
            )

        return embed.add_field(
            name="---", value="\n".join(self.get_lb_line(lb) for lb in lbs), inline=False
        )


class AkashaLbPaginator(BaseAkashaLbPaginator):
    def __init__(
        self,
        calculation_id: str,
        lb_embed: DefaultEmbed,
        you: akasha.Leaderboard | None,
        *,
        variant: str | None,
        uids: list[int],
        lb_size: int,
        lb_details: str,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(lb_embed, you, lb_size, lb_size, author=author, locale=locale)
        self.add_item(ShowLbDetailsButton(lb_details))

        self.calculation_id = calculation_id
        self.variant = variant
        self.uids = uids
        self.lbs: list[akasha.Leaderboard] = []

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
                calculation_id=int(self.calculation_id),
                page=self._current_page + 1,
                page_size=10,
                p=p,
                variant=self.variant,
                uids=self.uids,
                use_cache=True,
            )

        return Page(embed=self.get_page_embed(self.lbs))

    async def _update_page(
        self,
        i: Interaction,
        button: Button[PaginatorView] | None,
        *,
        type_: Literal["next", "prev", "first", "last", "start"],
        followup: bool = False,
        ephemeral: bool = False,
    ) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=ephemeral)

        self._pages[self._current_page] = await self.fetch_page(type_)
        return await super()._update_page(
            i, button, type_=type_, followup=followup, ephemeral=ephemeral
        )


class ShowLbDetailsButton(Button[AkashaLbPaginator]):
    def __init__(self, details: str) -> None:
        super().__init__(label=LocaleStr(key="akasha_show_details"), row=1)
        self.details = details

    async def callback(self, i: Interaction) -> None:
        await i.response.send_message(self.details, ephemeral=True)
