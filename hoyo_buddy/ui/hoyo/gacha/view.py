from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias

from hoyo_buddy.bot.config import CONFIG
from hoyo_buddy.constants import (
    BANNER_GUARANTEE_NUMS,
    BANNER_TYPE_NAMES,
    BANNER_WIN_RATE_TITLES,
    STANDARD_END_DATES,
    STANDARD_ITEMS,
    WEB_APP_URLS,
)
from hoyo_buddy.db import GachaHistory, GachaStats, HoyoAccount, get_dyk, get_last_gacha_num
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CURRENCY_EMOJIS
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import NoGachaLogFoundError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.web_app.schema import GachaParams

if TYPE_CHECKING:
    import asyncpg
    from discord import Locale

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

        banner_type = next(iter(BANNER_TYPE_NAMES[account.game]), None)
        if banner_type is None:
            msg = "No banner types found"
            raise ValueError(msg)
        self.banner_type = banner_type

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
        return f"{WEB_APP_URLS[CONFIG.env]}/gacha_log?{params.to_query_string()}"

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
        """Calculate the 50/50 stats for the current banner.
        See this image for more information: https://img.seria.moe/JPRHdRVOMVzYGYvR.png

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

        is_standards: list[bool] = []
        for item in five_stars:
            is_standard = item.item_id in STANDARD_ITEMS[self.account.game]
            if self.account.game in STANDARD_END_DATES:
                end_date = STANDARD_END_DATES[self.account.game].get(item.item_id)
                if end_date is not None and item.time.date() < end_date:
                    is_standard = False
            is_standards.append(is_standard)

        status: list[Literal[50, 100]] = [50]  # First pull is always 50% guaranteed
        wins = 0

        for i, is_standard in enumerate(is_standards):
            status.append(100 if is_standard else 50)  # Add guarantee status of next pull
            if status[i] == 50 and not is_standard:
                # If this pull's guarantee status is 50% and it's not a standard item, it's a win
                wins += 1
        del status[-1]  # Remove the last status as there isn't a next pull

        return wins, status.count(50)

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

        bangboo_channel_pulls = await self.get_pulls_count(banner_type=5)
        lifetime_currency = (lifetime_pulls - bangboo_channel_pulls) * 160

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

        # Bangboo channel pulls are free
        is_bangboo_channel = self.banner_type == 5 and self.account.game == Game.ZZZ
        banner_total_currency = 0 if is_bangboo_channel else banner_total_pulls * 160

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
            lifetime_currency=f"{lifetime_currency:,}",
            currency_emoji=CURRENCY_EMOJIS[self.account.game],
            total_pulls=banner_total_pulls,
            total_currency=f"{banner_total_currency:,}",
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
