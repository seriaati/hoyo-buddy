from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db.models import FarmNotify, HoyoAccount
from hoyo_buddy.db.models.notif_settings import AccountNotifSettings
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.reminders import notes
from hoyo_buddy.ui.reminders.farm import FarmReminderContainer, get_farm_item_names
from hoyo_buddy.ui.reminders.notes import ReminderContainer
from hoyo_buddy.ui.reminders.web_events import WebEventsReminderContainer

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hoyo_buddy.enums import Game, Locale
    from hoyo_buddy.types import Interaction, User


class ReminderCategory(StrEnum):
    NOTES = "reminder_settings_title"
    FARM = "farm_reminder_title"
    WEB_EVENTS = "web_events_reminder_title"


CATEGORY_GAMES: dict[ReminderCategory, Iterable[Game]] = {
    ReminderCategory.NOTES: notes.SUPPORT_GAMES,
    ReminderCategory.FARM: COMMANDS["farm reminder"].games or (),
    ReminderCategory.WEB_EVENTS: COMMANDS["web-events"].games or (),
}


class CategorySelect(ui.Select["RemindersView"]):
    def __init__(self, current: ReminderCategory) -> None:
        super().__init__(
            options=[
                ui.SelectOption(
                    label=LocaleStr(key=category.value),
                    value=category.value,
                    default=category == current,
                )
                for category in ReminderCategory
            ]
        )

    async def callback(self, i: Interaction) -> None:
        self.view.category = ReminderCategory(self.values[0])
        await self.view.update(i)


class AccountSelect(ui.Select["RemindersView"]):
    def __init__(self, *, current: HoyoAccount, accounts: list[HoyoAccount]) -> None:
        super().__init__(
            placeholder=LocaleStr(key="account_select_placeholder"),
            options=[
                ui.SelectOption(
                    label=str(account),
                    value=str(account.id),
                    emoji=get_game_emoji(account.game),
                    default=current.id == account.id,
                )
                for account in accounts
            ],
        )
        self.accounts = accounts

    async def callback(self, i: Interaction) -> None:
        self.view.account = next(acc for acc in self.accounts if str(acc.id) == self.values[0])
        await self.view.update(i)


class RemindersView(ui.LayoutView):
    def __init__(self, *, author: User, locale: Locale, account: HoyoAccount | None = None) -> None:
        """Reminders hub.

        Args:
            author: The user who invoked the view.
            locale: The locale to render in.
            account: If given, only the real-time notes reminders of this account are shown,
                without the account and category selectors.
        """
        super().__init__(author=author, locale=locale)

        self.category = ReminderCategory.NOTES
        self.locked = account is not None
        self.accounts: list[HoyoAccount] = []
        self.account: HoyoAccount
        if account is not None:
            self.account = account

    async def _set_accounts(self, user_id: int) -> None:
        games = CATEGORY_GAMES[self.category]
        accounts = [acc for acc in await HoyoAccount.filter(user_id=user_id) if acc.game in games]
        if not accounts:
            raise NoAccountFoundError(games)

        self.accounts = accounts
        if not hasattr(self, "account") or self.account not in accounts:
            self.account = next((acc for acc in accounts if acc.current), accounts[0])

    async def _get_container(self, i: Interaction) -> ui.Container:
        if self.category is ReminderCategory.NOTES:
            return await ReminderContainer.for_account(self.account)

        if self.category is ReminderCategory.FARM:
            farm_notify, _ = await FarmNotify.get_or_create(account=self.account)
            item_names = get_farm_item_names(
                farm_notify.item_ids, autofill=i.client.search_autofill, locale=self.locale
            )
            return FarmReminderContainer(farm_notify=farm_notify, item_names=item_names)

        if self.category is ReminderCategory.WEB_EVENTS:
            notif_settings, _ = await AccountNotifSettings.get_or_create(account=self.account)
            return WebEventsReminderContainer(notif_settings=notif_settings)

        msg = f"Unknown reminder category: {self.category}"
        raise ValueError(msg)

    async def update(self, i: Interaction) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=True)

        if not self.locked:
            await self._set_accounts(i.user.id)

        container = await self._get_container(i)

        if not self.locked:
            container.add_item(
                discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large)
            )
            container.add_item(
                ui.ActionRow(AccountSelect(current=self.account, accounts=self.accounts))
            )
            container.add_item(
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small)
            )
            container.add_item(ui.ActionRow(CategorySelect(self.category)))

        self.clear_items()
        self.add_item(container)

        self.message = await i.edit_original_response(view=self)
