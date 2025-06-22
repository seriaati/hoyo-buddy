from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from hoyo_buddy.db import FarmNotify, HoyoAccount, Settings
from hoyo_buddy.db.utils import draw_locale
from hoyo_buddy.models import DrawInput

from ..embeds import ErrorEmbed
from ..enums import Game, Locale
from ..exceptions import AutocompleteNotDoneYetError, InvalidQueryError
from ..hoyo.clients import ambr
from ..l10n import LocaleStr
from ..ui.hoyo.genshin.farm_notify import FarmNotifyView

if TYPE_CHECKING:
    from ..types import Interaction


class Action(IntEnum):
    ADD = 1
    REMOVE = 2


class FarmCommand:
    def __init__(
        self,
        interaction: Interaction,
        account: HoyoAccount,
        settings: Settings,
        locale: Locale,
        query: str | None = None,
        action: Action | None = None,
    ) -> None:
        self._interaction = interaction
        self._account = account
        self._choices = interaction.client.autocomplete_choices
        self._query = query
        self._settings = settings
        self._action = action
        self.locale = locale

        characters = self._choices[Game.GENSHIN][ambr.ItemCategory.CHARACTERS]
        weapons = self._choices[Game.GENSHIN][ambr.ItemCategory.WEAPONS]
        if not characters or not weapons:
            raise AutocompleteNotDoneYetError

        self._valid_item_ids = {c.value for c_choices in characters.values() for c in c_choices} | {
            c.value for w_choices in weapons.values() for c in w_choices
        }

    def _validate_query(self) -> None:
        if self._query is None:
            return
        if self._query == "none" or self._query not in self._valid_item_ids:
            raise InvalidQueryError

    async def _check_item_in_list(self, farm_notify: FarmNotify) -> bool:
        if self._query in farm_notify.item_ids:
            embed = ErrorEmbed(
                self.locale,
                title=LocaleStr(key="farm_add_command.item_already_in_list"),
                description=LocaleStr(key="farm_add_command.item_already_in_list_description"),
            )
            await self._interaction.followup.send(embed=embed)
            return True
        return False

    async def _get_farm_notify(self) -> FarmNotify:
        farm_notify, _ = await FarmNotify.get_or_create(account=self._account)
        await farm_notify.fetch_related("account")
        return farm_notify

    async def _update_farm_notify(self, farm_notify: FarmNotify) -> None:
        await farm_notify.filter(account=self._account).update(item_ids=farm_notify.item_ids)

    async def _start_view(self, farm_notify: FarmNotify) -> None:
        i = self._interaction
        view = FarmNotifyView(
            farm_notify,
            DrawInput(
                dark_mode=self._settings.dark_mode,
                locale=draw_locale(self.locale, farm_notify.account),
                session=i.client.session,
                filename="farm_notify.png",
                executor=i.client.executor,
                loop=i.client.loop,
            ),
            author=self._interaction.user,
            locale=self.locale,
        )
        await view.start(self._interaction)

    async def run(self) -> None:
        await self._interaction.response.defer()

        self._validate_query()

        farm_notify = await self._get_farm_notify()
        if self._action is not Action.REMOVE and await self._check_item_in_list(farm_notify):
            return

        if self._query is not None:
            if self._action is Action.ADD:
                farm_notify.item_ids.append(self._query)
            elif self._action is Action.REMOVE:
                try:
                    farm_notify.item_ids.remove(self._query)
                except ValueError:
                    embed = ErrorEmbed(
                        self.locale,
                        title=LocaleStr(key="farm_remove_command.item_not_found"),
                        description=LocaleStr(key="farm_remove_command.item_not_found_description"),
                    )
                    await self._interaction.followup.send(embed=embed)
                    return

            await self._update_farm_notify(farm_notify)

        await self._start_view(farm_notify)
