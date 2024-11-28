from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from hoyo_buddy.db.models import HoyoAccount, Leaderboard, get_locale, update_lb_ranks
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, LeaderboardType
from hoyo_buddy.exceptions import FeatureNotImplementedError, LeaderboardNotFoundError
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.ui.hoyo.leaderboard.others import LbPaginator
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin
    from asyncpg import Pool

    from hoyo_buddy.types import Interaction

LB_ORDERS: dict[LeaderboardType, Literal["ASC", "DESC"]] = {
    LeaderboardType.ACHIEVEMENT: "DESC",
    LeaderboardType.CHEST: "DESC",
    LeaderboardType.ABYSS_DMG: "DESC",
    LeaderboardType.THEATER_DMG: "DESC",
    LeaderboardType.MAX_FRIENDSHIP: "DESC",
}


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
    async def fetch_abyss_dmg(account: HoyoAccount) -> genshin.models.AbyssRankCharacter | None:
        cur_abyss = await account.client.get_genshin_spiral_abyss(account.uid)
        prev_abyss = await account.client.get_genshin_spiral_abyss(account.uid, previous=True)

        try:
            cur_dmg = cur_abyss.ranks.strongest_strike[0]
        except IndexError:
            cur_dmg = None

        try:
            prev_dmg = prev_abyss.ranks.strongest_strike[0]
        except IndexError:
            prev_dmg = None

        return max(cur_dmg, prev_dmg, key=lambda x: x.value if x is not None else 0)

    @staticmethod
    async def fetch_theater_dmg(account: HoyoAccount) -> genshin.models.BattleStatCharacter | None:
        cur_theater = await account.client.get_imaginarium_theater(account.uid)
        prev_theater = await account.client.get_imaginarium_theater(account.uid, previous=True)

        dmgs: list[genshin.models.BattleStatCharacter] = []

        for datas in (cur_theater.datas, prev_theater.datas):
            for data in datas:
                if not data.has_data or data.battle_stats is None:
                    continue

                character = data.battle_stats.max_damage_character
                if character is not None:
                    dmgs.append(character)

        if not dmgs:
            return None

        return max(dmgs, key=lambda x: x.value)

    @staticmethod
    async def fetch_chest_num(account: HoyoAccount) -> int:
        if account.game is Game.STARRAIL:
            user = await account.client.get_starrail_user(account.uid)
            return user.stats.chest_num

        partial_user = await account.client.get_partial_genshin_user(account.uid)
        stats = partial_user.stats
        return (
            stats.common_chests
            + stats.exquisite_chests
            + stats.luxurious_chests
            + stats.precious_chests
            + stats.remarkable_chests
        )

    @staticmethod
    async def fetch_max_friendship(account: HoyoAccount) -> int:
        characters = await account.client.get_genshin_characters(account.uid)
        return sum(character.friendship == 10 for character in characters)

    async def fetch_character_by_lb_type(
        self, account: HoyoAccount, lb_type: LeaderboardType
    ) -> genshin.models.AbyssRankCharacter | genshin.models.BattleStatCharacter | None:
        if lb_type is LeaderboardType.ABYSS_DMG:
            return await self.fetch_abyss_dmg(account)
        if lb_type is LeaderboardType.THEATER_DMG:
            return await self.fetch_theater_dmg(account)

        raise LeaderboardNotFoundError

    async def fetch_value_by_lb_type(self, account: HoyoAccount, lb_type: LeaderboardType) -> float:
        if lb_type is LeaderboardType.ACHIEVEMENT:
            return await self.fetch_achievement_num(account)
        if lb_type is LeaderboardType.CHEST:
            return await self.fetch_chest_num(account)
        if lb_type is LeaderboardType.MAX_FRIENDSHIP:
            return await self.fetch_max_friendship(account)

        raise LeaderboardNotFoundError

    @staticmethod
    async def get_lb_size(type_: LeaderboardType, game: Game) -> int:
        return await Leaderboard.filter(type=type_, game=game).count()

    @staticmethod
    def get_games_by_lb_type(lb_type: LeaderboardType) -> Sequence[Game]:
        if lb_type in {
            LeaderboardType.ABYSS_DMG,
            LeaderboardType.THEATER_DMG,
            LeaderboardType.MAX_FRIENDSHIP,
        }:
            return (Game.GENSHIN,)
        if lb_type is LeaderboardType.CHEST:
            return (Game.GENSHIN, Game.STARRAIL)
        if lb_type is LeaderboardType.ACHIEVEMENT:
            return (Game.GENSHIN, Game.STARRAIL, Game.ZZZ, Game.HONKAI)
        return ()

    @staticmethod
    def process_value(value: float) -> str:
        value = int(value)
        return f"{value:,}"

    async def run(
        self, i: Interaction, *, lb_type: LeaderboardType, account: HoyoAccount | None
    ) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        locale = await get_locale(i)

        account = account or await i.client.get_account(
            i.user.id, self.get_games_by_lb_type(lb_type)
        )
        await self.update_lb_data(pool=i.client.pool, lb_type=lb_type, account=account)

        lb_size = await self.get_lb_size(lb_type, account.game)
        embed = (
            DefaultEmbed(locale, title=EnumStr(lb_type))
            .set_author(name=EnumStr(account.game), icon_url=get_game_icon(account.game))
            .set_footer(text=LocaleStr(key="akasha_total_entries", total=lb_size))
        )

        you = await Leaderboard.get_or_none(type=lb_type, game=account.game, uid=account.uid)

        if lb_type in {LeaderboardType.ABYSS_DMG, LeaderboardType.THEATER_DMG}:
            async with AmbrAPIClient(locale) as api:
                characters = await api.fetch_characters()
                character_names = {char.id: char.name for char in characters}
        else:
            character_names = {}

        view = LbPaginator(
            embed,
            you,
            lb_size=lb_size,
            order=LB_ORDERS[lb_type],
            process_value=self.process_value,
            character_names=character_names,
            game=account.game,
            lb_type=lb_type,
            author=i.user,
            locale=locale,
        )
        await view.start(i)

    async def update_lb_data(
        self, *, pool: Pool, lb_type: LeaderboardType, account: HoyoAccount
    ) -> dict[str, str] | None:
        if lb_type in {LeaderboardType.ABYSS_DMG, LeaderboardType.THEATER_DMG}:
            character = await self.fetch_character_by_lb_type(account, lb_type)

            if character is None:
                value = 0
                extra_info = None
            else:
                value = character.value
                extra_info = {"id": character.id, "icon": character.icon}

        else:
            value = await self.fetch_value_by_lb_type(account, lb_type)
            extra_info = None

        if value > 0:
            await Leaderboard.update_or_create(
                type_=lb_type,
                game=account.game,
                uid=account.uid,
                value=value,
                username=account.username,
                extra_info=extra_info,
            )
            await update_lb_ranks(pool, game=account.game, type_=lb_type, order=LB_ORDERS[lb_type])
