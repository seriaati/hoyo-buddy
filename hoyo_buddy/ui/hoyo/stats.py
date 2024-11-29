from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hoyo_buddy.db.models import HoyoAccount, get_dyk
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.icons import get_game_icon

from ...embeds import DefaultEmbed
from ...emojis import get_game_emoji
from ...l10n import EnumStr, LocaleStr
from ...utils import blur_uid
from ..components import Select, SelectOption, View

if TYPE_CHECKING:
    import genshin
    from discord import Locale
    from genshin.models import RecordCard

    from hoyo_buddy.types import User

    from ...types import Interaction


def get_label(card: RecordCard) -> str:
    if not card.nickname:
        return blur_uid(card.uid)
    return f"{card.nickname} ({blur_uid(card.uid)})"


class StatsView(View):
    def __init__(
        self, accounts: list[HoyoAccount], current_account_id: int, *, author: User, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.accounts = accounts
        self.account = next((acc for acc in accounts if acc.uid == current_account_id), accounts[0])
        self.add_item(AccountSwitcher(accounts, self.account))

    def _get_user_embed(
        self, *, level: int, fields: dict[str, Any], avatar: str | None
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=self.account.blurred_display,
            description=LocaleStr(key="N_level", mi18n_game=Game.GENSHIN, N=level),
        )
        for key, value in fields.items():
            embed.add_field(name=LocaleStr(key=key, mi18n_game=self.account.game), value=str(value))

        embed.set_thumbnail(url=avatar)
        embed.set_author(name=EnumStr(self.account.game), icon_url=get_game_icon(self.account.game))
        return embed

    def get_genshin_user_embed(
        self, genshin_user: genshin.models.PartialGenshinUserStats
    ) -> DefaultEmbed:
        stats = genshin_user.stats
        fields = {
            "active_day": stats.days_active,
            "achievement_complete_count": stats.achievements,
            "card_avatar_number": stats.characters,
            "card_spriral_abyss": stats.spiral_abyss,
            "full_fetter_avatar_num": stats.max_friendship_characters,
            "unlock_portal": stats.unlocked_waypoints,
            "unlock_secret_area": stats.unlocked_domains,
            "wind_god": stats.anemoculi,
            "geoculus": stats.geoculi,
            "electroculus": stats.electroculi,
            "dendroculus": stats.dendroculi,
            "hydro_god": stats.hydroculi,
            "pyroculus_number": stats.pyroculi,
            "magnificent_treasure_box_count": stats.luxurious_chests,
            "rarity_treasure_box_count": stats.precious_chests,
            "delicacy_treasure_box_count": stats.exquisite_chests,
            "general_treasure_box_count": stats.common_chests,
            "magic_chest_number": stats.remarkable_chests,
        }
        return self._get_user_embed(
            level=genshin_user.info.level, fields=fields, avatar=genshin_user.info.in_game_avatar
        )

    def get_hsr_user_embed(self, user: genshin.models.StarRailUserStats) -> DefaultEmbed:
        stats = user.stats
        fields = {
            "hsr_active_day": stats.active_days,
            "hsr_get_account_count": stats.avatar_num,
            "hsr_achievement_complete_count": stats.achievement_num,
            "hsr_all_chest_count": stats.chest_num,
            "hsr_dream_paster_num": stats.dreamscape_pass_sticker,
        }
        return self._get_user_embed(
            level=user.info.level, fields=fields, avatar=user.in_game_avatar
        )

    def get_zzz_user_embed(
        self, user: genshin.models.ZZZUserStats, card: genshin.models.RecordCard
    ) -> DefaultEmbed:
        stats = user.stats
        fields = {
            "active_days": stats.active_days,
            "avatar_num": stats.character_num,
            "buddy_num": stats.bangboo_obtained,
            "cur_period_zone_layer_count": stats.shiyu_defense_frontiers,
            "achievement_count": stats.achievement_count,
            "commemorative_coins_list": stats.hia_coin.num,
        }
        return self._get_user_embed(level=card.level, fields=fields, avatar=user.in_game_avatar)

    def get_honkai_user_embed(self, user: genshin.models.HonkaiUserStats) -> DefaultEmbed:
        stats = user.stats
        fields = {
            "active_day_number": stats.active_days,
            "suit_number": stats.outfits,
            "armor_number": stats.battlesuits,
            "sss_armor_number": stats.battlesuits_SSS,
            "weapon_number": stats.weapons,
            "weapon_number_5": stats.weapons_5star,
            "stigmata_number": stats.stigmata,
            "stigmata_number_5": stats.stigmata_5star,
            "explain_text_2": stats.abyss.score,
            "explain_text_4": stats.memorial_arena.score,
        }
        return self._get_user_embed(
            level=user.info.level, fields=fields, avatar=user.info.in_game_avatar
        )

    async def start(self, i: Interaction, *, acc_select: AccountSwitcher | None = None) -> None:
        client = self.account.client
        client.set_lang(self.locale)

        if self.account.game is Game.GENSHIN:
            user = await client.get_partial_genshin_user(self.account.uid)
            embed = self.get_genshin_user_embed(user)
        elif self.account.game is Game.STARRAIL:
            user = await client.get_starrail_user(self.account.uid)
            embed = self.get_hsr_user_embed(user)
        elif self.account.game is Game.ZZZ:
            record_cards = await client.get_record_cards()
            card = next((card for card in record_cards if card.uid == self.account.uid), None)
            if card is None:
                msg = f"Record card not found for {self.account.uid}"
                raise ValueError(msg)

            user = await client.get_zzz_user(self.account.uid)
            embed = self.get_zzz_user_embed(user, card)
        elif self.account.game is Game.HONKAI:
            user = await client.get_honkai_user(self.account.uid)
            embed = self.get_honkai_user_embed(user)
        else:
            raise FeatureNotImplementedError(game=self.account.game)

        if acc_select is not None:
            await acc_select.unset_loading_state(i, embed=embed)
        else:
            await i.followup.send(embed=embed, view=self, content=await get_dyk(i))

        self.message = await i.original_response()


class AccountSwitcher(Select[StatsView]):
    def __init__(self, accounts: list[HoyoAccount], account: HoyoAccount) -> None:
        super().__init__(
            placeholder=LocaleStr(key="account_select_placeholder"),
            options=[
                SelectOption(
                    label=acc.blurred_display,
                    value=f"{acc.uid}_{acc.game}",
                    emoji=get_game_emoji(acc.game),
                    default=acc == account,
                )
                for acc in accounts
            ],
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        uid, game = self.values[0].split("_")
        account = next(
            (acc for acc in self.view.accounts if acc.uid == int(uid) and acc.game == game), None
        )
        if account is None:
            msg = f"Account not found for {uid} in {game}"
            raise ValueError(msg)

        self.view.account = account
        await self.view.start(i, acc_select=self)
