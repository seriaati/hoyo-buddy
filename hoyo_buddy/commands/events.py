from __future__ import annotations

from typing import TYPE_CHECKING

import hb_data

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db import HoyoAccount, Settings
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.enums import Game
from hoyo_buddy.models.zzz_event import ZZZEventCalendar, ZZZGachaEventWeapon, ZZZWeaponGachaEvent
from hoyo_buddy.ui.hoyo.event_calendar import EventCalendarView
from hoyo_buddy.ui.hoyo.events import EventsView
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from ..types import Interaction, User


class EventsCommand:
    @staticmethod
    async def run(i: Interaction, *, user: User, account: HoyoAccount | None) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        settings = await Settings.get(user_id=i.user.id)
        locale = await get_locale(i)

        user = user or i.user
        account = account or await i.client.get_account(
            user.id, games=COMMANDS["events"].games, platform=COMMANDS["events"].platform
        )

        client = account.client
        client.set_lang(locale)

        if account.game is Game.GENSHIN:
            calendar = await client.get_genshin_event_calendar(account.uid)
        elif account.game is Game.STARRAIL:
            calendar = await client.get_starrail_event_calendar()
        elif account.game is Game.ZZZ:
            async with hb_data.ZZZClient() as d_client:
                weapon_names = {weapon.id: weapon.name for weapon in d_client.get_weapons()}

            events = await client.get_zzz_event_calendar(account.uid)
            gacha_calendar = await client.get_zzz_gacha_calendar(account.uid)

            weapon_banners: list[ZZZWeaponGachaEvent] = []

            for banner in gacha_calendar.weapons:
                banner_weapons: list[ZZZGachaEventWeapon] = []

                for weapon in banner.weapons:
                    name = weapon_names.get(weapon.id, "???")
                    banner_weapons.append(
                        ZZZGachaEventWeapon.model_construct(
                            _fields_set=weapon.__pydantic_fields_set__,
                            **weapon.model_dump(),
                            name=name,
                        )
                    )

                weapon_banners.append(
                    ZZZWeaponGachaEvent.model_construct(
                        _fields_set=banner.__pydantic_fields_set__,
                        **banner.model_dump(exclude={"weapons"}),
                        weapons=banner_weapons,
                    )
                )

            calendar = ZZZEventCalendar(
                events=events, characters=gacha_calendar.characters, weapons=weapon_banners
            )
        else:
            calendar = None

        if calendar is not None:
            view = EventCalendarView(
                calendar, account, author=i.user, locale=locale, dark_mode=settings.dark_mode
            )
        else:
            view = EventsView(account, author=i.user, locale=locale)
        await view.start(i)
