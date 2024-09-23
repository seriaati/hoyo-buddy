from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Literal

from hoyo_buddy.db.models import Leaderboard
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.paginator import Page, PaginatorView
from hoyo_buddy.utils import blur_uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from discord import Locale

    from hoyo_buddy.embeds import DefaultEmbed
    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction, User


class LbPaginator(PaginatorView):
    def __init__(
        self,
        embed: DefaultEmbed,
        you: Leaderboard,
        *,
        lb_size: int,
        order: Literal["ASC", "DESC"],
        process_value: Callable[[float], Any],
        author: User,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__([], author=author, locale=locale, translator=translator)

        self.lb_embed = embed
        self.you = you
        self.lb_size = lb_size
        self.order = order
        self.process_value = process_value

        self.lbs: list[Leaderboard] = []
        self._max_page = math.ceil(lb_size / 10)

    def get_lb_line(self, lb: Leaderboard) -> str:
        value = self.process_value(lb.value)
        return f"{lb.rank}. {lb.username} ({blur_uid(lb.uid, arterisk='X')}) - **{value}**"

    def get_page_embed(self, lbs: list[Leaderboard]) -> DefaultEmbed:
        embed = self.lb_embed.copy()

        top_percent = LocaleStr(
            key="top_percent", percent=round(self.you.rank / self.lb_size * 100, 1)
        ).translate(self.translator, self.locale)
        you_str = LocaleStr(key="akasha_you").translate(self.translator, self.locale)

        embed.add_field(
            name=f"{you_str} ({top_percent})", value=self.get_lb_line(self.you), inline=False
        )

        return embed.add_field(
            name="---", value="\n".join(self.get_lb_line(lb) for lb in lbs), inline=False
        )

    async def fetch_page(self) -> Page:
        self.lbs = (
            await Leaderboard.filter(game=self.you.game, type=self.you.type)
            .order_by(f"{'rank' if self.order == 'DESC' else '-rank'}")
            .limit(10)
            .offset(self._current_page * 10)
        )
        return Page(embed=self.get_page_embed(self.lbs))

    async def _update_page(
        self, i: Interaction, *, followup: bool = False, ephemeral: bool = False
    ) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=ephemeral)

        try:
            self._pages[self._current_page]
        except IndexError:
            self._pages.insert(self._current_page, await self.fetch_page())

        return await super()._update_page(i, followup=followup, ephemeral=ephemeral)
