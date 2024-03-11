from datetime import timedelta
from typing import TYPE_CHECKING

from discord import Locale, Member, User

from ...bot.translator import LocaleStr, Translator
from ...constants import UID_TZ_OFFSET, WEEKDAYS
from ...draw.main_funcs import draw_farm_card
from ...embeds import DefaultEmbed
from ...hoyo.clients.ambr_client import AmbrAPIClient
from ...models import DrawInput, FarmData
from ...utils import get_now
from ..components import Select, SelectOption, View

if TYPE_CHECKING:
    import ambr

    from ...bot.bot import INTERACTION


class FarmView(View):
    def __init__(
        self,
        uid: int | None,
        dark_mode: bool,
        *,
        author: User | Member | None,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._uid = uid
        self._dark_mode = dark_mode

        self._weekday: int = 0
        self._determine_weekday()

        self.add_item(WeekdaySelect(self._weekday))

    def _determine_weekday(self) -> None:
        for uid_start, offset in UID_TZ_OFFSET.items():
            if str(self._uid).startswith(uid_start):
                self._weekday = (get_now() + timedelta(hours=offset)).weekday()
                break
        else:
            self._weekday = get_now().weekday()

    def _get_domains(self, domains: "ambr.Domains") -> list["ambr.Domain"]:
        match self._weekday:
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
            case _:
                msg = "Invalid weekday"
                raise ValueError(msg)

    async def _get_farm_data(self) -> list["FarmData"]:
        async with AmbrAPIClient(Locale.american_english, self.translator) as client:
            domains = await client.fetch_domains()
            upgrades = await client.fetch_upgrade_data()
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()

        farm_datas: list["FarmData"] = []

        domains_ = self._get_domains(domains)
        for domain in domains_:
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

    async def start(self, i: "INTERACTION") -> None:
        if self._weekday == 6:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Every domain is available on Sundays", key="farm_view.sundays"),
                description=LocaleStr("Happy farming!", key="farm_view.happy_farming"),
            )
            return await i.response.send_message(embed=embed, view=self)

        await i.response.defer()

        draw_input = DrawInput(
            dark_mode=self._dark_mode,
            locale=self.locale,
            session=i.client.session,
            filename="farm.webp",
        )
        file_ = await draw_farm_card(draw_input, await self._get_farm_data(), self.translator)

        await i.edit_original_response(attachments=[file_], view=self)
        self.message = await i.original_response()


class WeekdaySelect(Select[FarmView]):
    def __init__(self, current: int) -> None:
        super().__init__(
            placeholder=LocaleStr("Select a weekday", key="farm_view.weekday_select.placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr(label, warn_no_key=False),
                    value=str(value),
                    default=value == current,
                )
                for value, label in WEEKDAYS.items()
            ],
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._weekday = int(self.values[0])
        self.update_options_defaults()
        await self.view.start(i)
