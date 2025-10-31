from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, Literal, TypeAlias

import genshin
from loguru import logger

from hoyo_buddy import emojis
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    BANNER_FIVE_STAR_GUARANTEE_NUMS,
    BANNER_WIN_RATE_TITLES,
    MW_BANNER_TYPES,
    MW_EVENT_BANNER_TYPES,
    STANDARD_ITEMS,
    WEB_APP_URLS,
)
from hoyo_buddy.db import GachaHistory, GachaStats, HoyoAccount, get_dyk, get_last_gacha_num
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CURRENCY_EMOJIS
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import NoGachaLogFoundError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.l10n import BANNER_TYPE_NAMES, LocaleStr
from hoyo_buddy.ui import Button, Select, SelectOption, View
from hoyo_buddy.utils import ephemeral
from hoyo_buddy.utils.gacha import (
    check_gi_item_is_standard,
    check_hsr_item_is_standard,
    check_zzz_item_is_standard,
    fetch_gi_banners,
    fetch_hsr_banners,
)
from hoyo_buddy.web_app.schema import GachaParams

if TYPE_CHECKING:
    import aiohttp
    import asyncpg

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.models.gacha import GIBanner, HSRBanner
    from hoyo_buddy.types import Interaction, User


GlobalStat: TypeAlias = Literal[
    "lifetime_pulls", "avg_5star_pulls", "avg_4star_pulls", "avg_3star_pulls", "win_rate"
]
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
    "avg_3star_pulls": "ASC",
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
        self.add_item(GoToWebAppButton(self.get_web_app_url()))

    def get_web_app_url(self) -> str:
        params = GachaParams(
            locale=self.locale.value,
            account_id=self.account.id,
            banner_type=self.banner_type,
            rarities=[2, 3, 4, 5],
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

    async def calc_50_50_stats(self, session: aiohttp.ClientSession) -> tuple[int, int]:
        """Calculate the 50/50 stats for the current banner.
        See this image for more information: https://img.seria.moe/JPRHdRVOMVzYGYvR.png

        Returns:
            The number of 50/50 wins and the total number of 50/50 tries.
        """
        five_stars = (
            await GachaHistory.filter(account=self.account, rarity=5, banner_type=self.banner_type)
            .order_by("wish_id")
            .only("item_id", "time", "banner_id")
        )
        if not five_stars:
            return 0, 0

        gi_banners: list[GIBanner] = []
        item_names: dict[int, str] = {}
        if self.account.game is Game.GENSHIN:
            gi_banners = await fetch_gi_banners(session)
            async with AmbrAPIClient() as ambr:
                item_names = await ambr.fetch_item_id_to_name_map()

        hsr_banners: list[HSRBanner] = []
        if self.account.game is Game.STARRAIL:
            hsr_banners = await fetch_hsr_banners(session)

        is_standards: list[bool] = []
        for item in five_stars:
            if self.account.game is Game.GENSHIN:
                is_standard = check_gi_item_is_standard(item, gi_banners, item_names)
            elif self.account.game is Game.STARRAIL:
                is_standard = check_hsr_item_is_standard(item, hsr_banners)
            elif self.account.game is Game.ZZZ:
                is_standard = check_zzz_item_is_standard(item)
            else:
                logger.error(f"Unknown game for checking is_standard: {self.account.game}")
                continue

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

    async def get_stats_embed(
        self, pool: asyncpg.Pool, session: aiohttp.ClientSession
    ) -> DefaultEmbed:
        lifetime_pulls = await self.get_pulls_count()
        if lifetime_pulls == 0:
            raise NoGachaLogFoundError

        is_standard_ode = (
            self.banner_type == genshin.models.MWBannerType.STANDARD
            and self.account.game is Game.GENSHIN
        )

        # Bangboo channel pulls don't cost currency
        bangboo_channel_pulls = await self.get_pulls_count(banner_type=5)
        lifetime_currency = (lifetime_pulls - bangboo_channel_pulls) * 160

        last_gacha_num = await get_last_gacha_num(self.account, banner=self.banner_type)

        # Five star pity
        if not is_standard_ode:  # Standard Ode only pulls 4 and 3 star items
            last_five_star_num = await get_last_gacha_num(
                self.account, banner=self.banner_type, rarity=5
            )
            current_five_star_pity = last_gacha_num - last_five_star_num
            max_five_star_pity = BANNER_FIVE_STAR_GUARANTEE_NUMS[self.account.game][
                self.banner_type
            ]
        else:
            last_five_star_num = 0
            current_five_star_pity = 0
            max_five_star_pity = 0

        # Four star pity
        last_four_star_num = await get_last_gacha_num(
            self.account, banner=self.banner_type, rarity=4
        )
        current_four_star_pity = last_gacha_num - last_four_star_num
        # Standard Ode has a 70 pull pity for 4 stars
        max_four_star_pity = 70 if is_standard_ode else 10
        if not is_standard_ode and current_four_star_pity > max_four_star_pity:
            current_four_star_pity = last_gacha_num - last_five_star_num

        # Three star pity
        if is_standard_ode:  # Standard Ode can pull 3 star items
            last_three_star_num = await get_last_gacha_num(
                self.account, banner=self.banner_type, rarity=3
            )
            current_three_star_pity = last_gacha_num - last_three_star_num
            max_three_star_pity = 5
            if current_three_star_pity > max_three_star_pity:
                current_three_star_pity = last_gacha_num - last_four_star_num
        else:
            last_three_star_num = 0
            current_three_star_pity = 0
            max_three_star_pity = 0

        # 50/50 win rate
        banner_wins, banner_5stars = await self.calc_50_50_stats(session)

        # Average pulls per 5-star and 4-star
        total_five_stars = await self.get_pulls_count(rarity=5, banner_type=self.banner_type)
        total_four_stars = await self.get_pulls_count(rarity=4, banner_type=self.banner_type)
        total_three_stars = await self.get_pulls_count(rarity=3, banner_type=self.banner_type)
        banner_total_pulls = await self.get_pulls_count(banner_type=self.banner_type)

        # Bangboo channel pulls are free
        is_bangboo_channel = self.banner_type == 5 and self.account.game == Game.ZZZ
        banner_total_currency = 0 if is_bangboo_channel else banner_total_pulls * 160

        five_star_avg_pulls = banner_total_pulls / total_five_stars if total_five_stars else 0
        four_star_avg_pulls = banner_total_pulls / total_four_stars if total_four_stars else 0
        three_star_avg_pulls = banner_total_pulls / total_three_stars if total_three_stars else 0

        await GachaStats.create_or_update(
            account=self.account,
            lifetime_pulls=lifetime_pulls,
            win_rate=banner_wins / banner_5stars if banner_5stars else 0,
            avg_5star_pulls=five_star_avg_pulls,
            avg_4star_pulls=four_star_avg_pulls,
            avg_3star_pulls=three_star_avg_pulls,
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

        if self.banner_type in MW_BANNER_TYPES and self.account.game is Game.GENSHIN:
            if self.banner_type in MW_EVENT_BANNER_TYPES:
                currency_emoji = emojis.ARCANE_EMOJI
            else:
                currency_emoji = emojis.GEODE_EMOJI
        else:
            currency_emoji = CURRENCY_EMOJIS[self.account.game]

        # Personal stats
        personal_stats_parts: list[str] = []
        pity_data = {
            "gacha_log_personal_stats_pity": {
                5: (current_five_star_pity, max_five_star_pity),
                4: (current_four_star_pity, max_four_star_pity),
                3: (current_three_star_pity, max_three_star_pity),
            },
            "gacha_log_personal_stats_rarity_total": {
                5: total_five_stars,
                4: total_four_stars,
                3: total_three_stars,
            },
            "gacha_log_personal_stats_rarity_average": {
                5: five_star_avg_pulls,
                4: four_star_avg_pulls,
                3: three_star_avg_pulls,
            },
        }

        # The total pulls on MW banners are already lifetime pulls for that banner
        if self.banner_type not in MW_BANNER_TYPES:
            personal_stats_parts.append(
                LocaleStr(
                    key="gacha_log_personal_stats_lifetime",
                    pulls=lifetime_pulls,
                    currency=f"{lifetime_currency:,}",
                    emoji=currency_emoji,
                ).translate(self.locale)
            )

        personal_stats_parts.append(
            LocaleStr(
                key="gacha_log_personal_stats_banner_total",
                pulls=banner_total_pulls,
                currency=f"{banner_total_currency:,}",
                emoji=currency_emoji,
            ).translate(self.locale)
        )

        # Standard Ode only drops 4 and 3 star items
        first_rarity = 4 if is_standard_ode else 5
        second_rarity = first_rarity - 1
        rarities_to_show = {first_rarity, second_rarity}

        for part_key, rarity_data in pity_data.items():
            for rarity, data in rarity_data.items():
                if rarity in rarities_to_show:
                    if part_key == "gacha_log_personal_stats_pity":
                        cur, max_ = data
                        part = LocaleStr(key=part_key, rarity=rarity, cur=cur, max=max_).translate(
                            self.locale
                        )
                    elif part_key == "gacha_log_personal_stats_rarity_total":
                        total = data
                        part = LocaleStr(key=part_key, rarity=rarity, total=total).translate(
                            self.locale
                        )
                    elif part_key == "gacha_log_personal_stats_rarity_average":
                        avg = round(data, 1)
                        part = LocaleStr(key=part_key, rarity=rarity, avg=avg).translate(
                            self.locale
                        )
                    else:
                        continue

                    personal_stats_parts.append(part)

        personal_stats = "\n".join(personal_stats_parts)

        # Global stats
        global_stats_parts: list[str] = []

        global_stats_parts.append(
            LocaleStr(
                key="gacha_log_global_stats_lifetime",
                lifetime=await self.get_ranking_str(pool, stat="lifetime_pulls"),
            ).translate(self.locale)
        )

        if 5 in rarities_to_show:
            global_stats_parts.append(
                LocaleStr(
                    key="gacha_log_global_stats_luck",
                    rarity=5,
                    luck=await self.get_ranking_str(pool, stat="avg_5star_pulls"),
                ).translate(self.locale)
            )

        if 4 in rarities_to_show:
            global_stats_parts.append(
                LocaleStr(
                    key="gacha_log_global_stats_luck",
                    rarity=4,
                    luck=await self.get_ranking_str(pool, stat="avg_4star_pulls"),
                ).translate(self.locale)
            )

        if 3 in rarities_to_show:
            global_stats_parts.append(
                LocaleStr(
                    key="gacha_log_global_stats_luck",
                    rarity=3,
                    luck=await self.get_ranking_str(pool, stat="avg_3star_pulls"),
                ).translate(self.locale)
            )

        global_stats = "\n".join(global_stats_parts)

        if (title := BANNER_WIN_RATE_TITLES[self.account.game].get(self.banner_type)) is not None:
            personal_win_rate_stats = LocaleStr(
                key="win_rate_stats",
                title=title,
                win_rate=round(banner_wins / banner_5stars * 100, 2) if banner_5stars else 0,
                wins=banner_wins,
                total=banner_5stars,
            ).translate(self.locale)
            personal_stats += f"{personal_win_rate_stats}"

            global_win_rate_stats = LocaleStr(
                key="win_rate_global_stats",
                title=title,
                win_rate=await self.get_ranking_str(pool, stat="win_rate"),
            ).translate(self.locale)
            global_stats += f"{global_win_rate_stats}"

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
        embed = await self.get_stats_embed(i.client.pool, i.client.session)
        await i.followup.send(embed=embed, view=self, content=await get_dyk(i))
        self.message = await i.original_response()


class BannerTypeSelector(Select[ViewGachaLogView]):
    def __init__(self, game: Game, *, current: int) -> None:
        super().__init__(
            placeholder=LocaleStr(key="gacha_log_view_banner_type_selector_placeholder"),
            options=[
                SelectOption(label=name, value=str(banner_type), default=banner_type == current)
                for banner_type, name in BANNER_TYPE_NAMES[game].items()
            ],
        )

    async def callback(self, i: Interaction) -> Any:
        self.view.banner_type = int(self.values[0])
        await i.response.defer(ephemeral=ephemeral(i))
        embed = await self.view.get_stats_embed(i.client.pool, i.client.session)
        self.update_options_defaults()

        button: GoToWebAppButton | None = next(
            (c for c in self.view.children if isinstance(c, Button) and c.url is not None),
            None,  # pyright: ignore[reportAssignmentType]
        )
        if button is not None:
            button.url = self.view.get_web_app_url()
        await i.edit_original_response(embed=embed, view=self.view)


class GoToWebAppButton(Button[ViewGachaLogView]):
    def __init__(self, url: str) -> None:
        super().__init__(label=LocaleStr(key="gacha_log_view_full"), url=url)
