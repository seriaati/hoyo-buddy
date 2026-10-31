from __future__ import annotations

from itertools import starmap
from typing import TYPE_CHECKING, Any

from hoyo_buddy import emojis, ui
from hoyo_buddy.api.schemas import GachaParams
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS, MW_BANNER_TYPES, MW_EVENT_BANNER_TYPES
from hoyo_buddy.db import draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import draw_gacha_summary_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CURRENCY_EMOJIS
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.gacha_summary import build_gacha_summary, fetch_player_avatar
from hoyo_buddy.l10n import BANNER_TYPE_NAMES, LocaleStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui import Button, Select, SelectOption
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    import discord

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.models.gacha_summary import GachaRank, GachaSummary
    from hoyo_buddy.types import Interaction, User

CARD_FILENAME = "gacha_summary.webp"


class ViewGachaLogView(ui.LayoutView):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account

        banner_type = next(iter(BANNER_TYPE_NAMES[account.game]), None)
        if banner_type is None:
            msg = "No banner types found"
            raise ValueError(msg)
        self.banner_type = banner_type

        self.web_app_button = GoToWebAppButton(self.get_web_app_url())
        self._rows: list[list[Any]] = [
            [BannerTypeSelector(account.game, current=self.banner_type)],
            [self.web_app_button],
        ]
        self._avatar_url: str | None = None
        self.dyk = ""

    def get_web_app_url(self) -> str:
        params = GachaParams(
            locale=self.locale.value,
            account_id=self.account.id,
            banner_type=self.banner_type,
            rarities=[2, 3, 4, 5],
        )
        return f"{FRONTEND_URLS[CONFIG.env]}/gacha_log?{params.to_query_string()}"

    def render(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(ui.EmbedContainer(embed, *starmap(ui.ActionRow, self._rows)))
        if self.dyk:
            self.add_item(ui.TextDisplay(self.dyk))

    def get_ranking_str(self, rank: GachaRank | None) -> str:
        if rank is None:
            return "N/A"

        top_percent = LocaleStr(key="top_percent", percent=rank.percent).translate(self.locale)
        return f"{top_percent} ({rank.rank}/{rank.total})"

    @property
    def shows_card(self) -> bool:
        # Miliastra Wonderland banners don't drop 5 stars
        return not (self.account.game is Game.GENSHIN and self.banner_type in MW_BANNER_TYPES)

    async def build(self, i: Interaction) -> tuple[DefaultEmbed, discord.File | None]:
        if self._avatar_url is None:
            self._avatar_url = await fetch_player_avatar(self.account) or i.user.display_avatar.url

        summary = await build_gacha_summary(
            self.account,
            banner_type=self.banner_type,
            pool=i.client.pool,
            locale=self.locale,
            avatar_url=self._avatar_url,
        )
        embed = self.get_stats_embed(summary)
        if not self.shows_card:
            return embed, None

        file_ = await draw_gacha_summary_card(
            DrawInput(
                dark_mode=False,
                locale=draw_locale(self.locale, self.account),
                session=i.client.session,
                filename=CARD_FILENAME,
                executor=i.client.executor,
                loop=i.client.loop,
            ),
            summary,
        )
        embed.set_image(url=f"attachment://{CARD_FILENAME}")
        return embed, file_

    def get_stats_embed(self, summary: GachaSummary) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(key="gacha_log_stats_title"),
            description=LocaleStr(
                key="star5_guaranteed" if summary.guaranteed else "star5_no_guaranteed"
            )
            if summary.win_rate_title is not None
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
                5: (summary.five_star_pity, summary.five_star_max_pity),
                4: (summary.four_star_pity, summary.four_star_max_pity),
                3: (summary.three_star_pity, summary.three_star_max_pity),
            },
            "gacha_log_personal_stats_rarity_total": {
                5: summary.total_five_stars,
                4: summary.total_four_stars,
                3: summary.total_three_stars,
            },
            "gacha_log_personal_stats_rarity_average": {
                5: summary.avg_five_star_pulls,
                4: summary.avg_four_star_pulls,
                3: summary.avg_three_star_pulls,
            },
        }

        # The total pulls on MW banners are already lifetime pulls for that banner
        if self.banner_type not in MW_BANNER_TYPES:
            personal_stats_parts.append(
                LocaleStr(
                    key="gacha_log_personal_stats_lifetime",
                    pulls=summary.lifetime_pulls,
                    currency=f"{summary.lifetime_currency:,}",
                    emoji=currency_emoji,
                ).translate(self.locale)
            )

        personal_stats_parts.append(
            LocaleStr(
                key="gacha_log_personal_stats_banner_total",
                pulls=summary.banner_pulls,
                currency=f"{summary.banner_currency:,}",
                emoji=currency_emoji,
            ).translate(self.locale)
        )

        # Standard Ode only drops 4 and 3 star items
        first_rarity = 4 if summary.is_standard_ode else 5
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
        global_stats_parts: list[str] = [
            LocaleStr(
                key="gacha_log_global_stats_lifetime",
                lifetime=self.get_ranking_str(summary.lifetime_rank),
            ).translate(self.locale)
        ]

        luck_ranks = {
            5: summary.five_star_luck_rank,
            4: summary.four_star_luck_rank,
            3: summary.three_star_luck_rank,
        }
        for rarity, luck_rank in luck_ranks.items():
            if rarity in rarities_to_show:
                global_stats_parts.append(
                    LocaleStr(
                        key="gacha_log_global_stats_luck",
                        rarity=rarity,
                        luck=self.get_ranking_str(luck_rank),
                    ).translate(self.locale)
                )

        global_stats = "\n".join(global_stats_parts)

        if (title := summary.win_rate_title) is not None:
            wins, total = summary.fifty_fifty_wins, summary.fifty_fifty_total
            personal_win_rate_stats = LocaleStr(
                key="win_rate_stats",
                title=title,
                win_rate=round(wins / total * 100, 2) if total else 0,
                wins=wins,
                total=total,
            ).translate(self.locale)
            personal_stats += f"\n{personal_win_rate_stats}"

            global_win_rate_stats = LocaleStr(
                key="win_rate_global_stats",
                title=title,
                win_rate=self.get_ranking_str(summary.win_rate_rank),
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
        self.dyk = await get_dyk(i)
        embed, file_ = await self.build(i)
        self.render(embed)
        if file_ is None:
            await i.followup.send(view=self)
        else:
            await i.followup.send(view=self, file=file_)
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
        await self.set_loading_state(i)
        embed, file_ = await self.view.build(i)
        self.view.web_app_button.url = self.view.get_web_app_url()
        self.view.render(embed)
        await self.unset_loading_state(i, attachments=[file_] if file_ is not None else [])


class GoToWebAppButton(Button[ViewGachaLogView]):
    def __init__(self, url: str) -> None:
        super().__init__(label=LocaleStr(key="gacha_log_view_full"), url=url)
