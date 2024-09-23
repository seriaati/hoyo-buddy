from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import HoyoAccount, Leaderboard, get_locale, update_lb_ranks
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, LeaderboardType
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.ui.hoyo.leaderboard.others import LbPaginator
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction, User


class LeaderboardCommand:
    @staticmethod
    async def fetch_achievement_num(account: HoyoAccount) -> int:
        client = account.client

        if account.game is Game.GENSHIN:
            partial_user = await client.get_partial_genshin_user(account.uid)
            return partial_user.stats.achievements
        if account.game is Game.STARRAIL:
            user = await client.get_starrail_user(account.uid)
            return user.stats.achievement_num
        if account.game is Game.HONKAI:
            user = await client.get_honkai_user(account.uid)
            return user.stats.achievements
        if account.game is Game.ZZZ:
            user = await client.get_zzz_user(account.uid)
            return user.stats.achievement_count

        raise FeatureNotImplementedError(game=account.game)

    @staticmethod
    async def get_lb_size(type_: LeaderboardType, game: Game) -> int:
        return await Leaderboard.filter(type=type_, game=game).count()

    async def achievement(self, i: Interaction, *, user: User, account: HoyoAccount | None) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        user = user or i.user
        account = account or await i.client.get_account(
            user.id, (Game.GENSHIN, Game.STARRAIL, Game.HONKAI, Game.ZZZ)
        )
        achievement_num = await self.fetch_achievement_num(account)

        await Leaderboard.update_or_create(
            type_=LeaderboardType.ACHIEVEMENT,
            game=account.game,
            uid=account.uid,
            value=achievement_num,
            username=account.username,
        )
        await update_lb_ranks(
            i.client.pool, game=account.game, type_=LeaderboardType.ACHIEVEMENT, order="DESC"
        )

        locale = await get_locale(i)
        embed = DefaultEmbed(
            locale, i.client.translator, title=LocaleStr(key="achievement_lb_title")
        ).set_author(name=EnumStr(account.game), icon_url=get_game_icon(account.game))

        you = await Leaderboard.get(
            type=LeaderboardType.ACHIEVEMENT, game=account.game, uid=account.uid
        )
        lb_size = await self.get_lb_size(LeaderboardType.ACHIEVEMENT, account.game)

        view = LbPaginator(
            embed,
            you,
            lb_size=lb_size,
            order="DESC",
            process_value=int,
            author=i.user,
            locale=locale,
            translator=i.client.translator,
        )
        await view.start(i)
