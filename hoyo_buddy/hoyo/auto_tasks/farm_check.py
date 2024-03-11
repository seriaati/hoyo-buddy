from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar, TypeVar

import ambr
from discord import Locale

from ...bot.translator import LocaleStr, Translator
from ...constants import UID_TZ_OFFSET
from ...db.models import FarmNotify
from ...embeds import DefaultEmbed
from ...utils import get_now
from ..farm_data import FarmDataFetcher

if TYPE_CHECKING:
    from ...bot.bot import HoyoBuddy

CharacterOrWeapon = TypeVar("CharacterOrWeapon", ambr.Character, ambr.Weapon)


class FarmChecker:
    _bot: ClassVar["HoyoBuddy"]
    _translator: ClassVar[Translator]

    @classmethod
    async def _notify_user(cls, item: CharacterOrWeapon, farm_notify: FarmNotify) -> None:
        embed = DefaultEmbed(
            farm_notify.account.user.settings.locale or Locale.american_english,
            cls._translator,
            title=LocaleStr(
                "Materials for {name} is farmable today",
                key="farm_check.farmable_today",
                name=item.name,
            ),
        )
        embed.set_thumbnail(url=item.icon)
        embed.set_footer(
            text=LocaleStr(
                "Use /farm reminder to configure reminder settings\nUse /farm view to view all items farmable today",
                key="farm_check.use_farm_notify",
            )
        )
        embed.set_author(name=str(farm_notify.account), icon_url=farm_notify.account.game_icon)

        message = await cls._bot.dm_user(farm_notify.account.user.id, embed=embed)
        if message is None:
            await FarmNotify.filter(account=farm_notify.account).update(enabled=False)

    @classmethod
    async def _fetch_related_data(cls, farm_notify: FarmNotify) -> None:
        await farm_notify.account.fetch_related("user")
        await farm_notify.account.user.fetch_related("settings")

    @classmethod
    async def _check_and_notify(
        cls, item_id: str, items: list[CharacterOrWeapon], farm_notify: FarmNotify
    ) -> bool:
        for item in items:
            if str(item.id) == item_id:
                await cls._notify_user(item, farm_notify)
                return True
        return False

    @classmethod
    async def execute(cls, bot: "HoyoBuddy", uid_start: str) -> None:
        cls._bot = bot
        cls._translator = bot.translator

        farm_notifies = await FarmNotify.filter(enabled=True).all().prefetch_related("account")
        weekday = (get_now() + timedelta(hours=UID_TZ_OFFSET.get(uid_start, 0))).weekday()

        for farm_notify in farm_notifies:
            if not str(farm_notify.account.uid).startswith(uid_start):
                continue

            await cls._fetch_related_data(farm_notify)
            locale = farm_notify.account.user.settings.locale

            farm_datas = await FarmDataFetcher.fetch(weekday, bot.translator, locale=locale)

            for item_id in farm_notify.item_ids:
                for farm_data in farm_datas:
                    if await cls._check_and_notify(item_id, farm_data.characters, farm_notify):
                        break
                    if await cls._check_and_notify(item_id, farm_data.weapons, farm_notify):
                        break
