from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

from ..db.models import FarmNotify, HoyoAccount, Settings
from ..embeds import ErrorEmbed
from ..enums import Game
from ..exceptions import AutocompleteNotDoneYetError, InvalidQueryError
from ..hoyo.clients import ambr
from ..l10n import LocaleStr
from ..ui.hoyo.farm_notify import FarmNotifyView
from ..utils import ephemeral

if TYPE_CHECKING:
    import discord

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
        query: str | None = None,
        action: Action | None = None,
    ) -> None:
        self._interaction = interaction
        self._account = account
        self._choices = interaction.client.autocomplete_choices
        self._query = query
        self._settings = settings
        self._translator = interaction.client.translator
        self._action = action

        try:
            characters = self._choices[Game.GENSHIN][ambr.ItemCategory.CHARACTERS]
            weapons = self._choices[Game.GENSHIN][ambr.ItemCategory.WEAPONS]
        except KeyError as e:
            raise AutocompleteNotDoneYetError from e

        self._valid_item_ids = {id_ for c in characters.values() for id_ in c.values()} | {
            id_ for w in weapons.values() for id_ in w.values()
        }

    @property
    def locale(self) -> discord.Locale:
        return self._settings.locale or self._interaction.locale

    def _validate_query(self) -> None:
        if self._query is None:
            return
        if self._query == "none" or self._query not in self._valid_item_ids:
            raise InvalidQueryError

    async def _check_item_in_list(self, farm_notify: FarmNotify) -> bool:
        if self._query in farm_notify.item_ids:
            embed = ErrorEmbed(
                self.locale,
                self._translator,
                title=LocaleStr(key="farm_add_command.item_already_in_list"),
                description=LocaleStr(key="farm_add_command.item_already_in_list_description"),
            )
            await self._interaction.followup.send(
                embed=embed, ephemeral=ephemeral(self._interaction)
            )
            return True
        return False

    async def _get_farm_notify(self) -> FarmNotify:
        farm_notify, _ = await FarmNotify.get_or_create(account=self._account)
        await farm_notify.fetch_related("account")
        return farm_notify

    async def _update_farm_notify(self, farm_notify: FarmNotify) -> None:
        await farm_notify.filter(account=self._account).update(item_ids=farm_notify.item_ids)

    async def _start_view(self, farm_notify: FarmNotify) -> None:
        view = FarmNotifyView(
            farm_notify,
            self._settings.dark_mode,
            self._interaction.client.session,
            self._interaction.client.executor,
            self._interaction.client.loop,
            author=self._interaction.user,
            locale=self.locale,
            translator=self._translator,
        )
        await view.start(self._interaction)

    async def run(self) -> None:
        await self._interaction.response.defer(ephemeral=ephemeral(self._interaction))

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
                        self._translator,
                        title=LocaleStr(key="farm_remove_command.item_not_found"),
                        description=LocaleStr(key="farm_remove_command.item_not_found_description"),
                    )
                    await self._interaction.followup.send(embed=embed)
                    return

            await self._update_farm_notify(farm_notify)

        await self._start_view(farm_notify)
