from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, TypeVar

import ambr
from discord import Locale
from loguru import logger

from hoyo_buddy.constants import UID_TZ_OFFSET
from hoyo_buddy.db import FarmNotify
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.farm_data import FarmDataFetcher
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_now

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy


CharacterOrWeapon = TypeVar("CharacterOrWeapon", ambr.Character, ambr.Weapon)


class FarmChecker:
    def __init__(self, bot: HoyoBuddy) -> None:
        self._bot = bot
        self._item_id_to_name = {}
        """[locale][item_id] = item_name"""

    async def _notify_user(self, item: CharacterOrWeapon, farm_notify: FarmNotify) -> None:
        locale = farm_notify.account.user.settings.locale or Locale.american_english

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(
                key="farm_check.farmable_today",
                name=self._item_id_to_name[locale.value][str(item.id)],
            ),
        )
        embed.set_thumbnail(url=item.icon)
        embed.set_footer(text=LocaleStr(key="farm_check.use_farm_notify"))
        embed.add_acc_info(farm_notify.account, blur=False)

        _, errored = await self._bot.dm_user(farm_notify.account.user.id, embed=embed)
        if errored:
            await FarmNotify.filter(account=farm_notify.account).update(enabled=False)

    async def _check_and_notify(
        self, item_id: str, items: list[CharacterOrWeapon], farm_notify: FarmNotify
    ) -> bool:
        for item in items:
            if str(item.id) == item_id:
                await self._notify_user(item, farm_notify)
                return True
        return False

    async def execute(self, uid_start: str) -> None:
        try:  # noqa: PLR1702
            logger.info(f"Starting farm check task for uid_start {uid_start}")

            farm_notifies = await FarmNotify.filter(enabled=True).all().prefetch_related("account")
            if not farm_notifies:
                return

            weekday = (get_now() + timedelta(hours=UID_TZ_OFFSET.get(uid_start, 0))).weekday()
            farm_datas = await FarmDataFetcher.fetch(weekday)

            for farm_notify in farm_notifies:
                if not str(farm_notify.account.uid).startswith(uid_start):
                    continue

                await farm_notify.account.fetch_related("user", "user__settings")
                locale = farm_notify.account.user.settings.locale or Locale.american_english
                if locale.value not in self._item_id_to_name:
                    async with AmbrAPIClient(locale) as client:
                        characters = await client.fetch_characters()
                        weapons = await client.fetch_weapons()
                    self._item_id_to_name[locale.value] = {
                        str(item.id): item.name for item in characters + weapons
                    }

                notified: set[str] = set()

                for item_id in farm_notify.item_ids:
                    if item_id in notified:
                        continue

                    for farm_data in farm_datas:
                        if len(item_id) == 5:
                            # weapon
                            notified_ = await self._check_and_notify(
                                item_id, farm_data.weapons, farm_notify
                            )
                            if notified_:
                                notified.add(item_id)
                                break

                        else:
                            notified_ = await self._check_and_notify(
                                item_id, farm_data.characters, farm_notify
                            )
                            if notified_:
                                notified.add(item_id)
                                break
        except Exception as e:
            self._bot.capture_exception(e)
        finally:
            logger.info(f"Finished farm check task for uid_start {uid_start}")
