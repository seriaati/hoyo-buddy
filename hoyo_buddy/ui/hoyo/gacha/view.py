from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias

from hoyo_buddy.constants import (
    BANNER_GUARANTEE_NUMS,
    BANNER_TYPE_NAMES,
    BANNER_WIN_RATE_TITLES,
    STANDARD_END_DATES,
    STANDARD_ITEMS,
    WEB_APP_URLS,
)
from hoyo_buddy.db.models import GachaHistory, GachaStats, HoyoAccount, get_dyk, get_last_gacha_num
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CURRENCY_EMOJIS
from hoyo_buddy.exceptions import NoGachaLogFoundError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.web_app.schema import GachaParams

if TYPE_CHECKING:
    import asyncpg
    from discord import Locale

    from hoyo_buddy.enums import Game
    from hoyo_buddy.types import Interaction, User


GlobalStat: TypeAlias = Literal["lifetime_pulls", "avg_5star_pulls", "avg_4star_pulls", "win_rate"]
GET_RANKING_SQL = """
SELECT
    ranked.rank,
    (SELECT COUNT(*) FROM gachastats WHERE game = $1 AND banner_type = $3) AS total_rows
FROM (
    SELECT
        account_id,
        ROW_NUMBER() OVER (ORDER BY {row} {order}) as rank
    FROM gachastats
    WHERE game = $1 AND banner_type = $3
) ranked
WHERE account_id = $2;
"""

RANK_ORDERS: Final[dict[GlobalStat, Literal["ASC", "DESC"]]] = {
    "lifetime_pulls": "DESC",
    "avg_5star_pulls": "ASC",
    "avg_4star_pulls": "ASC",
    "win_rate": "DESC",
}


async def get_ranking(
    pool: asyncpg.Pool,
    *,
    game: Game,
    row: GlobalStat,
    order: Literal["ASC", "DESC"],
    account_id: int,
    banner_type: int,
) -> tuple[int, int]:
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            GET_RANKING_SQL.format(row=row, order=order), game.value, account_id, banner_type
        )


class ViewGachaLogView(View):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.banner_type = next(iter(BANNER_TYPE_NAMES[account.game]))

        self.add_item(BannerTypeSelector(account.game, current=self.banner_type))
        self.web_app_url = self.get_web_app_url()
        self.add_item(Button(label=LocaleStr(key="gacha_log_view_full"), url=self.web_app_url))

    def get_web_app_url(self) -> str:
        params = GachaParams(
            locale=self.locale.value,
            account_id=self.account.id,
            banner_type=self.banner_type,
            rarities=[3, 4, 5],
        )
        return f"{WEB_APP_URLS[os.environ['ENV']]}/gacha_log?{params.to_query_string()}"

    async def get_pulls_count(
        self, *, banner_type: int | None = None, rarity: int | None = None
    ) -> int:
        filter_kwargs: dict[str, Any] = {"account": self.account}
        if banner_type is not None:
            filter_kwargs["banner_type"] = banner_type
        if rarity is not None:
            filter_kwargs["rarity"] = rarity

        return await GachaHistory.filter(**filter_kwargs).count()

    async def calc_50_50_stats(self) -> tuple[int, int]:
        """Calculate the 50/50 stats for the current banner or all banners.
        If the player pulls two 5-star non-standard items in a row, it is considered a win.

        Returns:
            The number of 50/50 wins and the total number of 50/50 tries.
        """
        five_stars = (
            await GachaHistory.filter(account=self.account, rarity=5, banner_type=self.banner_type)
            .order_by("wish_id")
            .only("item_id", "time")
        )
        if not five_stars:
            return 0, 0

        if len(five_stars) == 1:
            if five_stars[0].item_id in STANDARD_ITEMS[self.account.game]:
                return 0, 0
            # If the only 5-star is not a standard item, it is considered a win
            return 1, 1

        is_standards: list[bool] = []
        for item in five_stars:
            is_standard = item.item_id in STANDARD_ITEMS[self.account.game]
            if self.account.game in STANDARD_END_DATES:
                end_date = STANDARD_END_DATES[self.account.game].get(item.item_id)
                if end_date is not None and item.time.date() < end_date:
                    is_standard = False
            is_standards.append(is_standard)

        win = 0
        for i, is_standard in enumerate(is_standards[1:], start=1):
            # Current one and previous one are both not standard items: win 50/50
            if not is_standard and not is_standards[i - 1]:
                win += 1

        return win, is_standards.count(False)

    async def guaranteed(self) -> bool:
        gacha = (
            await GachaHistory.filter(account=self.account, banner_type=self.banner_type, rarity=5)
            .first()
            .only("item_id")
        )
        if gacha is None:
            return False
        return gacha.item_id in STANDARD_ITEMS[self.account.game]

    async def get_ranking_str(self, pool: asyncpg.Pool, *, stat: GlobalStat) -> str:
        rank, total = await get_ranking(
            pool,
            game=self.account.game,
            row=stat,
            order=RANK_ORDERS[stat],
            account_id=self.account.id,
            banner_type=self.banner_type,
        )

        if rank == 0 or total == 0:
            return "N/A"

        top_percent = LocaleStr(key="top_percent", percent=round(rank / total * 100, 2)).translate(
            self.locale
        )
        return f"{top_percent} ({rank}/{total})"

    async def get_stats_embed(self, pool: asyncpg.Pool) -> DefaultEmbed:
        lifetime_pulls = await self.get_pulls_count()
        if lifetime_pulls == 0:
            raise NoGachaLogFoundError

        # Five star pity
        last_five_star_num = await get_last_gacha_num(
            self.account, banner=self.banner_type, rarity=5
        )
        last_gacha_num = await get_last_gacha_num(self.account, banner=self.banner_type)
        current_five_star_pity = last_gacha_num - last_five_star_num
        max_five_star_pity = BANNER_GUARANTEE_NUMS[self.account.game][self.banner_type]

        # Four star pity
        last_four_star_num = await get_last_gacha_num(
            self.account, banner=self.banner_type, rarity=4
        )
        current_four_star_pity = last_gacha_num - last_four_star_num

        # 50/50 win rate
        banner_wins, banner_5stars = await self.calc_50_50_stats()

        # Average pulls per 5-star and 4-star
        total_five_stars = await self.get_pulls_count(rarity=5, banner_type=self.banner_type)
        total_four_stars = await self.get_pulls_count(rarity=4, banner_type=self.banner_type)
        banner_total_pulls = await self.get_pulls_count(banner_type=self.banner_type)
        five_star_avg_pulls = banner_total_pulls / total_five_stars if total_five_stars else 0
        four_star_avg_pulls = banner_total_pulls / total_four_stars if total_four_stars else 0

        await GachaStats.create_or_update(
            account=self.account,
            lifetime_pulls=lifetime_pulls,
            win_rate=banner_wins / banner_5stars if banner_5stars else 0,
            avg_5star_pulls=five_star_avg_pulls,
            avg_4star_pulls=four_star_avg_pulls,
            banner_type=self.banner_type,
        )

        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_log_stats_title"),
            description=LocaleStr(
                key="star5_guaranteed" if await self.guaranteed() else "star5_no_guaranteed"
            )
            if self.banner_type in BANNER_WIN_RATE_TITLES[self.account.game]
            else None,
        )

        personal_stats = LocaleStr(
            key="gacha_log_personal_stats",
            lifetime_pulls=lifetime_pulls,
            lifetime_currency=f"{lifetime_pulls * 160:,}",
            currency_emoji=CURRENCY_EMOJIS[self.account.game],
            total_pulls=banner_total_pulls,
            total_currency=f"{banner_total_pulls * 160:,}",
            star5_pity_cur=current_five_star_pity,
            star5_pity_max=max_five_star_pity,
            star4_pity_cur=current_four_star_pity,
            total_star5=total_five_stars,
            total_star4=total_four_stars,
            avg_pulls_per_star5=round(five_star_avg_pulls, 1),
            avg_pulls_per_star4=round(four_star_avg_pulls, 1),
        ).translate(self.locale)

        global_stats = LocaleStr(
            key="gacha_log_global_stats",
            lifetime=await self.get_ranking_str(pool, stat="lifetime_pulls"),
            star5_luck=await self.get_ranking_str(pool, stat="avg_5star_pulls"),
            star4_luck=await self.get_ranking_str(pool, stat="avg_4star_pulls"),
        ).translate(self.locale)

        if (title := BANNER_WIN_RATE_TITLES[self.account.game].get(self.banner_type)) is not None:
            personal_win_rate_stats = LocaleStr(
                key="win_rate_stats",
                title=title,
                win_rate=round(banner_wins / banner_5stars * 100, 2) if banner_5stars else 0,
                wins=banner_wins,
                total=banner_5stars,
            ).translate(self.locale)
            personal_stats += f"\n{personal_win_rate_stats}"

            global_win_rate_stats = LocaleStr(
                key="win_rate_global_stats",
                title=title,
                win_rate=await self.get_ranking_str(pool, stat="win_rate"),
            ).translate(self.locale)
            global_stats += f"\n{global_win_rate_stats}"

        embed.add_field(
            name=LocaleStr(key="gacha_log_personal_stats_title"), value=personal_stats, inline=False
        )
        embed.add_field(
            name=LocaleStr(key="gacha_log_global_stats_title"), value=global_stats, inline=False
        )

        embed.add_acc_info(self.account)
        return embed

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        embed = await self.get_stats_embed(i.client.pool)
        await i.followup.send(embed=embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()


class BannerTypeSelector(Select[ViewGachaLogView]):
    def __init__(self, game: Game, *, current: int) -> None:
        super().__init__(
            placeholder=LocaleStr(key="gacha_log_view_banner_type_selector_placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr(key=key), value=str(banner_type), default=banner_type == current
                )
                for banner_type, key in BANNER_TYPE_NAMES[game].items()
            ],
        )

    async def callback(self, i: Interaction) -> Any:
        self.view.banner_type = int(self.values[0])
        await i.response.defer(ephemeral=ephemeral(i))
        embed = await self.view.get_stats_embed(i.client.pool)
        self.update_options_defaults()

        self.view.web_app_url = self.view.get_web_app_url()
        await i.edit_original_response(embed=embed, view=self.view)
