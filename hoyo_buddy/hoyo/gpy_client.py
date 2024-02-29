from typing import TYPE_CHECKING

import genshin

from ..bot.translator import LocaleStr, Translator
from ..constants import LOCALE_TO_GPY_LANG
from ..db.enums import GAME_CONVERTER, GAME_THUMBNAILS
from ..embeds import DefaultEmbed

if TYPE_CHECKING:
    from discord import Locale


class GenshinClient(genshin.Client):
    def __init__(
        self,
        cookies: str,
        *,
        uid: int | None = None,
        game: genshin.Game = genshin.Game.GENSHIN,
    ) -> None:
        super().__init__(cookies, game=game, uid=uid)

    def set_lang(self, locale: "Locale") -> None:
        self.lang = LOCALE_TO_GPY_LANG[locale]

    @staticmethod
    def get_daily_reward_embed(
        daily_reward: genshin.models.DailyReward,
        game: genshin.Game,
        locale: "Locale",
        translator: Translator,
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            locale,
            translator,
            title=LocaleStr("Daily check-in reward claimed", key="reward_claimed_title"),
            description=f"{daily_reward.name} x{daily_reward.amount}",
        )
        embed.set_thumbnail(url=daily_reward.icon)
        converted_game = GAME_CONVERTER[game]
        embed.set_author(
            name=LocaleStr(converted_game.value, warn_no_key=False),
            icon_url=GAME_THUMBNAILS[game],
        )
        return embed
