from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.db.models import Settings
from hoyo_buddy.db.models.hoyo_account import HoyoAccount
from hoyo_buddy.db.models.notif_settings import AccountNotifSettings
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.hoyo.auto_tasks import auto_mimo
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.settings.account import AccountSettingsContainer, MimoSettingsContainer
from hoyo_buddy.ui.settings.card import CardSettingsContainer
from hoyo_buddy.ui.settings.notification import (
    MimoNotificationSettingsContainer,
    NotificationSettingsContainer,
)
from hoyo_buddy.ui.settings.reminder import ReminderContainer
from hoyo_buddy.ui.settings.user import UserSettingsContainer

from ._common import AccountSelect

if TYPE_CHECKING:
    from hoyo_buddy.db.models.card_settings import CardSettings
    from hoyo_buddy.types import Interaction, User


class SettingsCategory(StrEnum):
    USER_SETTINGS = "user_settings_title"
    ACCOUNT_SETTINGS = "account_settings_title"
    MIMO_SETTINGS = "mimo_title"
    NOTIFICATION_SETTINGS = "notification_settings_button_label"
    MIMO_NOTIFICATION_SETTINGS = "mimo_notification_settings"
    REMINDER_SETTINGS = "reminder_settings_title"


ACCOUNT_SELECT_CATEGORIES: set[SettingsCategory] = {
    SettingsCategory.ACCOUNT_SETTINGS,
    SettingsCategory.MIMO_SETTINGS,
    SettingsCategory.NOTIFICATION_SETTINGS,
    SettingsCategory.MIMO_NOTIFICATION_SETTINGS,
    SettingsCategory.REMINDER_SETTINGS,
}


class CategorySelect(ui.Select["SettingsView"]):
    def __init__(self, current: SettingsCategory) -> None:
        super().__init__(
            options=[
                ui.SelectOption(
                    label=LocaleStr(key=category.value),
                    value=category.value,
                    default=category == current,
                )
                for category in SettingsCategory
            ]
        )

    async def callback(self, i: Interaction) -> None:
        self.view.category = SettingsCategory(self.values[0])
        await self.view.update(i)


class SettingsView(ui.LayoutView):
    def __init__(self, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)

        self.category = SettingsCategory.USER_SETTINGS

        # Attributes needed by containers
        self.settings: Settings
        self.account: HoyoAccount
        self.accounts: list[HoyoAccount]
        self.card_settings: CardSettings

    async def _get_container(self, **kwargs) -> ui.Container:
        account: HoyoAccount = kwargs.get("account")  # pyright: ignore[reportAssignmentType]
        settings: Settings = kwargs.get("settings")  # pyright: ignore[reportAssignmentType]

        if self.category is SettingsCategory.USER_SETTINGS:
            return UserSettingsContainer(settings=settings)

        if self.category is SettingsCategory.ACCOUNT_SETTINGS:
            return AccountSettingsContainer(account=account)

        if self.category is SettingsCategory.MIMO_SETTINGS:
            return MimoSettingsContainer(account=account)

        if self.category is SettingsCategory.NOTIFICATION_SETTINGS:
            return NotificationSettingsContainer(account=account)

        if self.category is SettingsCategory.MIMO_NOTIFICATION_SETTINGS:
            return MimoNotificationSettingsContainer(account=account)

        if self.category is SettingsCategory.REMINDER_SETTINGS:
            return await ReminderContainer.for_account(account)

        msg = f"Unknown settings category: {self.category}"
        raise ValueError(msg)

    async def _get_kwargs(self, i: Interaction) -> dict:
        if self.category is SettingsCategory.USER_SETTINGS:
            if hasattr(self, "settings"):
                return {"settings": self.settings}

            settings, _ = await Settings.get_or_create(user_id=i.user.id)
            return {"settings": settings}

        if self.category in ACCOUNT_SELECT_CATEGORIES:
            if hasattr(self, "accounts") and hasattr(self, "account"):
                account = self.account
                accounts = self.accounts
            else:
                accounts = await HoyoAccount.filter(user_id=i.user.id).prefetch_related(
                    "user", "notif_settings"
                )
                if not accounts:
                    raise NoAccountFoundError(list(Game))

                account = next((acc for acc in accounts if acc.current), accounts[0])

            if self.category in {
                SettingsCategory.MIMO_SETTINGS,
                SettingsCategory.MIMO_NOTIFICATION_SETTINGS,
            }:
                mimo_accounts = [acc for acc in accounts if acc.game in auto_mimo.SUPPORT_GAMES]
                account = next((acc for acc in mimo_accounts if acc.current), accounts[0])

            if self.category in {
                SettingsCategory.NOTIFICATION_SETTINGS,
                SettingsCategory.MIMO_NOTIFICATION_SETTINGS,
            }:
                for acc in accounts:
                    if acc.notif_settings is None:  # pyright: ignore[reportUnnecessaryComparison]
                        await AccountNotifSettings.create(account=acc)
                        await acc.fetch_related("notif_settings")  # pyright: ignore[reportGeneralTypeIssues]

            return {"account": account, "accounts": accounts}

        msg = f"Unknown settings category: {self.category}"
        raise ValueError(msg)

    def _set_kwargs(self, **kwargs) -> None:
        if self.category is SettingsCategory.USER_SETTINGS:
            self.settings = kwargs["settings"]

        if self.category in ACCOUNT_SELECT_CATEGORIES:
            self.account = kwargs["account"]
            self.accounts = kwargs["accounts"]

    async def update(self, i: Interaction) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=True)

        kwargs = await self._get_kwargs(i)
        self._set_kwargs(**kwargs)

        container = await self._get_container(**kwargs)
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large)
        )

        if self.category in ACCOUNT_SELECT_CATEGORIES:
            accounts = self.accounts
            if self.category is SettingsCategory.MIMO_SETTINGS:
                accounts = [acc for acc in accounts if acc.game in auto_mimo.SUPPORT_GAMES]

            container.add_item(ui.ActionRow(AccountSelect(current=self.account, accounts=accounts)))
            container.add_item(
                discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small)
            )

        container.add_item(ui.ActionRow(CategorySelect(self.category)))

        self.clear_items()
        self.add_item(container)

        self.message = await i.edit_original_response(view=self)


class CardSettingsView(ui.LayoutView):
    def __init__(
        self,
        *,
        card_settings: CardSettings,
        settings: Settings,
        character_name: str,
        game: Game,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.card_settings = card_settings
        self.settings = settings
        self.character_name = character_name
        self.game = game

    async def update(self, i: Interaction, *, followup: bool = False) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=True)

        container = CardSettingsContainer(
            card_settings=self.card_settings,
            settings=self.settings,
            character_name=self.character_name,
            game=self.game,
        )
        self.clear_items()
        self.add_item(container)

        if followup:
            self.message = await i.followup.send(view=self, ephemeral=True, wait=True)
        else:
            self.message = await i.edit_original_response(view=self)
