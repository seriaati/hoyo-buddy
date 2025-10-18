from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from hoyo_buddy import ui
from hoyo_buddy.db.models import Settings
from hoyo_buddy.db.models.hoyo_account import HoyoAccount
from hoyo_buddy.db.models.notif_settings import AccountNotifSettings
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.hoyo.auto_tasks import auto_mimo
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.settings.account import (
    AccountSettingsContainer,
    MimoSettingsContainer,
    NotificationSettingsContainer,
)
from hoyo_buddy.ui.settings.user import UserSettingsContainer

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction, User


class SettingsCategory(StrEnum):
    USER_SETTINGS = "user_settings_title"
    ACCOUNT_SETTINGS = "account_settings_title"
    MIMO_SETTINGS = "mimo_title"
    NOTIFICATION_SETTINGS = "notification_settings_button_label"


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

    def _get_container(self, **kwargs) -> ui.Container:
        if self.category is SettingsCategory.USER_SETTINGS:
            return UserSettingsContainer(**kwargs)

        if self.category is SettingsCategory.ACCOUNT_SETTINGS:
            return AccountSettingsContainer(**kwargs)

        if self.category is SettingsCategory.MIMO_SETTINGS:
            return MimoSettingsContainer(**kwargs)

        if self.category is SettingsCategory.NOTIFICATION_SETTINGS:
            return NotificationSettingsContainer(**kwargs)

        msg = f"Unknown settings category: {self.category}"
        raise ValueError(msg)

    async def _get_kwargs(self, i: Interaction) -> dict:
        if self.category is SettingsCategory.USER_SETTINGS:
            if hasattr(self, "settings"):
                return {"settings": self.settings}

            settings, _ = await Settings.get_or_create(user_id=i.user.id)
            return {"settings": settings}

        if self.category in {
            SettingsCategory.ACCOUNT_SETTINGS,
            SettingsCategory.MIMO_SETTINGS,
            SettingsCategory.NOTIFICATION_SETTINGS,
        }:
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

            if self.category is SettingsCategory.MIMO_SETTINGS:
                accounts = [acc for acc in accounts if acc.game in auto_mimo.SUPPORT_GAMES]
                account = next((acc for acc in accounts if acc.current), accounts[0])

            if self.category is SettingsCategory.NOTIFICATION_SETTINGS:
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

        if self.category is SettingsCategory.ACCOUNT_SETTINGS:
            self.account = kwargs["account"]
            self.accounts = kwargs["accounts"]

        if self.category is SettingsCategory.MIMO_SETTINGS:
            self.account = kwargs["account"]

        if self.category is SettingsCategory.NOTIFICATION_SETTINGS:
            self.account = kwargs["account"]
            self.accounts = kwargs["accounts"]

    async def update(self, i: Interaction) -> None:
        if not i.response.is_done():
            await i.response.defer(ephemeral=True)

        kwargs = await self._get_kwargs(i)
        self._set_kwargs(**kwargs)
        container = self._get_container(**kwargs)

        self.clear_items()
        container.add_item(ui.ActionRow(CategorySelect(self.category)))
        self.add_item(container)

        self.message = await i.edit_original_response(view=self)
