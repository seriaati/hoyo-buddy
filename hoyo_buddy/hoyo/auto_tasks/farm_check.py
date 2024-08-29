from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar, TypeVar

import ambr
from discord import Locale
from loguru import logger

from ...constants import UID_TZ_OFFSET
from ...db.models import FarmNotify
from ...embeds import DefaultEmbed
from ...l10n import LocaleStr, Translator
from ...utils import get_now
from ..clients.ambr import AmbrAPIClient
from ..farm_data import FarmDataFetcher

if TYPE_CHECKING:
    from ...bot import HoyoBuddy


CharacterOrWeapon = TypeVar("CharacterOrWeapon", ambr.Character, ambr.Weapon)


class FarmChecker:
    _bot: ClassVar[HoyoBuddy]
    _translator: ClassVar[Translator]
    _item_id_to_name: ClassVar[dict[str, dict[str, str]]]
    """[locale][item_id] = item_name"""

    @classmethod
    async def _notify_user(cls, item: CharacterOrWeapon, farm_notify: FarmNotify) -> None:
        locale = farm_notify.account.user.settings.locale or Locale.american_english

        embed = DefaultEmbed(
            locale,
            cls._translator,
            title=LocaleStr(
                key="farm_check.farmable_today",
                name=cls._item_id_to_name[locale.value][str(item.id)],
            ),
        )
        embed.set_thumbnail(url=item.icon)
        embed.set_footer(text=LocaleStr(key="farm_check.use_farm_notify"))
        embed.add_acc_info(farm_notify.account, blur=False)

        message = await cls._bot.dm_user(farm_notify.account.user.id, embed=embed)
        if message is None:
            await FarmNotify.filter(account=farm_notify.account).update(enabled=False)

    @classmethod
    async def _check_and_notify(
        cls, item_id: str, items: list[CharacterOrWeapon], farm_notify: FarmNotify,
    ) -> bool:
        for item in items:
            if str(item.id) == item_id:
                await cls._notify_user(item, farm_notify)
                return True
        return False

    @classmethod
    async def execute(cls, bot: HoyoBuddy, uid_start: str) -> None:
        logger.info(f"Starting farm check task for uid_start {uid_start}")

        cls._bot = bot
        cls._translator = bot.translator
        cls._item_id_to_name = {}

        farm_notifies = await FarmNotify.filter(enabled=True).all().prefetch_related("account")
        if not farm_notifies:
            return

        weekday = (get_now() + timedelta(hours=UID_TZ_OFFSET.get(uid_start, 0))).weekday()
        farm_datas = await FarmDataFetcher.fetch(weekday, bot.translator)

        for farm_notify in farm_notifies:
            if not str(farm_notify.account.uid).startswith(uid_start):
                continue

            await farm_notify.account.fetch_related("user", "user__settings")
            locale = farm_notify.account.user.settings.locale or Locale.american_english
            if locale.value not in cls._item_id_to_name:
                async with AmbrAPIClient(locale, bot.translator) as client:
                    characters = await client.fetch_characters()
                    weapons = await client.fetch_weapons()
                cls._item_id_to_name[locale.value] = {
                    str(item.id): item.name for item in characters + weapons
                }

            notified: set[str] = set()

            for item_id in farm_notify.item_ids:
                if item_id in notified:
                    continue

                for farm_data in farm_datas:
                    if len(item_id) == 5:
                        # weapon
                        notified_ = await cls._check_and_notify(
                            item_id, farm_data.weapons, farm_notify,
                        )
                        if notified_:
                            notified.add(item_id)
                            break

                    else:
                        notified_ = await cls._check_and_notify(
                            item_id, farm_data.characters, farm_notify,
                        )
                        if notified_:
                            notified.add(item_id)
                            break

        logger.info(f"Finished farm check task for uid_start {uid_start}")
