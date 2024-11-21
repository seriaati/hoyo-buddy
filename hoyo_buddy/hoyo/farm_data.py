from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Locale

from ..constants import AMBR_CITY_TO_CITY
from ..models import FarmData
from .clients.ambr import AmbrAPIClient

if TYPE_CHECKING:
    import ambr

    from ..enums import GenshinCity


class FarmDataFetcher:
    _weekday: int

    @classmethod
    def _get_domains(cls, domains: ambr.Domains) -> list[ambr.Domain]:
        match cls._weekday:
            case 0:
                return domains.monday
            case 1:
                return domains.tuesday
            case 2:
                return domains.wednesday
            case 3:
                return domains.thursday
            case 4:
                return domains.friday
            case 5:
                return domains.saturday
            case 6:
                return domains.sunday
            case _:
                msg = "Invalid weekday"
                raise ValueError(msg)

    @classmethod
    async def fetch(
        cls, weekday: int, *, locale: Locale | None = None, city: GenshinCity | None = None
    ) -> list[FarmData]:
        # Initialize class variables
        cls._weekday = weekday

        async with AmbrAPIClient(Locale.american_english) as client:
            domains = await client.fetch_domains()
        async with AmbrAPIClient(locale or Locale.american_english) as client:
            upgrades = await client.fetch_upgrade_data()
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()

        farm_datas: list[FarmData] = []

        domains_ = cls._get_domains(domains)
        for domain in domains_:
            if city is not None and AMBR_CITY_TO_CITY[domain.city] != city:
                continue
            farm_data = FarmData(domain)
            reward_ids = [r.id for r in domain.rewards]

            if "Mastery" in domain.name:
                # Character domains
                for upgrade in upgrades.character:
                    if any(item.id in reward_ids for item in upgrade.items):
                        character = next((c for c in characters if c.id == upgrade.id), None)
                        if character is None:
                            continue
                        farm_data.characters.append(character)
            else:
                # Weapon domains
                for upgrade in upgrades.weapon:
                    if any(item.id in reward_ids for item in upgrade.items):
                        weapon = next((w for w in weapons if str(w.id) == upgrade.id), None)
                        if weapon is None:
                            continue
                        farm_data.weapons.append(weapon)

            farm_datas.append(farm_data)

        return farm_datas
