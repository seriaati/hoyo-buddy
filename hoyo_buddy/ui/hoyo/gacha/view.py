from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from hoyo_buddy.constants import BANNER_GUARANTEES, BANNER_TYPE_NAMES, STANDARD_ITEMS, WEB_APP_URLS
from hoyo_buddy.db.models import GachaHistory, GachaStats, HoyoAccount, get_last_gacha_num
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CURRENCY_EMOJIS
from hoyo_buddy.exceptions import NoGachaLogFoundError
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.ui.components import Button, Select, SelectOption, View
from hoyo_buddy.utils import calc_top_percentage, ephemeral
from hoyo_buddy.web_app.schema import GachaParams

if TYPE_CHECKING:
    from discord import Locale

    from hoyo_buddy.enums import Game
    from hoyo_buddy.types import Interaction, User


class ViewGachaLogView(View):
    def __init__(
        self, account: HoyoAccount, *, author: User, locale: Locale, translator: Translator
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
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

    async def get_lifetime_pulls(self) -> int:
        return await GachaHistory.filter(account=self.account).count()

    async def get_banner_total_pulls(self) -> int:
        return await GachaHistory.filter(account=self.account, banner_type=self.banner_type).count()

    async def count_rarity_gacha_pulls(self, rarity: int, *, cur_banner_only: bool) -> int:
        filter_kwargs = {"account": self.account, "rarity": rarity}
        if cur_banner_only:
            filter_kwargs["banner_type"] = self.banner_type

        return await GachaHistory.filter(**filter_kwargs).count()

    async def calculate_50_50_win_rate(self, *, cur_banner_only: bool) -> float:
        filter_kwargs = {"account": self.account, "rarity": 5}
        if cur_banner_only:
            filter_kwargs["banner_type"] = self.banner_type

        five_stars = await GachaHistory.filter(**filter_kwargs).order_by("wish_id").only("item_id")
        if len(five_stars) < 2:
            return 0

        is_standards: list[bool] = [
            item.item_id in STANDARD_ITEMS[self.account.game] for item in five_stars
        ]
        win = 0
        for i, is_standard in enumerate(is_standards[1:], start=1):
            # Current one and previous one are both not standard items: win 50/50
            if not is_standard and not is_standards[i - 1]:
                win += 1

        return win / (len(is_standards) - 1)

    async def get_stats_embed(self) -> DefaultEmbed:
        lifetime_pulls = await self.get_lifetime_pulls()
        if lifetime_pulls == 0:
            raise NoGachaLogFoundError

        banner_total_pulls = await self.get_banner_total_pulls()

        last_5star_num = await get_last_gacha_num(self.account, banner=self.banner_type, rarity=5)
        last_num = await get_last_gacha_num(self.account, banner=self.banner_type)
        star5_pity_cur = last_num - last_5star_num
        star5_pity_max = BANNER_GUARANTEES[self.account.game][self.banner_type]

        last_4star_num = await get_last_gacha_num(self.account, banner=self.banner_type, rarity=4)
        star4_pity_cur = last_num - last_4star_num

        banner_win_rate = await self.calculate_50_50_win_rate(cur_banner_only=True)
        total_star5 = await self.count_rarity_gacha_pulls(5, cur_banner_only=True)
        total_star4 = await self.count_rarity_gacha_pulls(4, cur_banner_only=True)
        avg_pulls_per_star5 = banner_total_pulls / total_star5 if total_star5 else 0
        avg_pulls_per_star4 = banner_total_pulls / total_star4 if total_star4 else 0

        # Save gacha stats
        total_win_rate = await self.calculate_50_50_win_rate(cur_banner_only=False)
        stat_star5 = await self.count_rarity_gacha_pulls(5, cur_banner_only=False)
        stat_avg_star_5 = lifetime_pulls / stat_star5 if stat_star5 else 0
        stat_star4 = await self.count_rarity_gacha_pulls(4, cur_banner_only=False)
        stat_avg_star_4 = lifetime_pulls / stat_star4 if stat_star4 else 0
        await GachaStats.create_or_update(
            account=self.account,
            lifetime_pulls=lifetime_pulls,
            win_rate=total_win_rate,
            avg_5star_pulls=stat_avg_star_5,
            avg_4star_pulls=stat_avg_star_4,
        )

        embed = DefaultEmbed(
            self.locale, self.translator, title=LocaleStr(key="gacha_log_stats_title")
        )

        # Personal stats
        embed.add_field(
            name=LocaleStr(key="gacha_log_personal_stats_title"),
            value=LocaleStr(
                key="gacha_log_personal_stats",
                lifetime_pulls=lifetime_pulls,
                lifetime_currency=f"{lifetime_pulls * 160:,}",
                currency_emoji=CURRENCY_EMOJIS[self.account.game],
                total_pulls=banner_total_pulls,
                total_currency=f"{banner_total_pulls * 160:,}",
                star5_pity_cur=star5_pity_cur,
                star5_pity_max=star5_pity_max,
                star4_pity_cur=star4_pity_cur,
                win_rate=round(banner_win_rate * 100, 2),
                total_star5=total_star5,
                total_star4=total_star4,
                avg_pulls_per_star5=int(avg_pulls_per_star5),
                avg_pulls_per_star4=int(avg_pulls_per_star4),
            ),
            inline=False,
        )

        # Global stats
        all_gacha_stats = await GachaStats.filter(game=self.account.game)

        lifetime_pulls_percentage = calc_top_percentage(
            lifetime_pulls, [x.lifetime_pulls for x in all_gacha_stats], reverse=True
        )
        star_5_luck_percentage = calc_top_percentage(
            stat_avg_star_5, [x.avg_5star_pulls for x in all_gacha_stats], reverse=False
        )
        star_4_luck_percentage = calc_top_percentage(
            stat_avg_star_4, [x.avg_4star_pulls for x in all_gacha_stats], reverse=False
        )
        win_rate_percentage = calc_top_percentage(
            total_win_rate, [x.win_rate for x in all_gacha_stats], reverse=True
        )
        embed.add_field(
            name=LocaleStr(key="gacha_log_global_stats_title"),
            value=LocaleStr(
                key="gacha_log_global_stats",
                lifetime=lifetime_pulls_percentage,
                star5_luck=star_5_luck_percentage,
                star4_luck=star_4_luck_percentage,
                win_rate=win_rate_percentage,
            ),
            inline=False,
        )

        embed.add_acc_info(self.account)
        return embed

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        embed = await self.get_stats_embed()
        await i.followup.send(embed=embed, view=self)
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
        await i.response.defer()
        embed = await self.view.get_stats_embed()
        self.update_options_defaults()

        self.view.web_app_url = self.view.get_web_app_url()
        await i.edit_original_response(embed=embed, view=self.view)
