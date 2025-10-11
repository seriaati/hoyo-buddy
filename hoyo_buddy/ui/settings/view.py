from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from hoyo_buddy import ui
from hoyo_buddy.db.models import Settings
from hoyo_buddy.db.models.hoyo_account import HoyoAccount
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.settings.account import AccountSettingsContainer
from hoyo_buddy.ui.settings.user import UserSettingsContainer

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction, User


class SettingsCategory(StrEnum):
    USER_SETTINGS = "user_settings_title"
    ACCOUNT_SETTINGS = "account_settings_title"


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

        msg = f"Unknown settings category: {self.category}"
        raise ValueError(msg)

    async def _get_kwargs(self, i: Interaction) -> dict:
        if self.category is SettingsCategory.USER_SETTINGS:
            if hasattr(self, "settings"):
                return {"settings": self.settings}

            settings, _ = await Settings.get_or_create(user_id=i.user.id)
            return {"settings": settings}

        if self.category is SettingsCategory.ACCOUNT_SETTINGS:
            if hasattr(self, "accounts") and hasattr(self, "account"):
                return {"account": self.account, "accounts": self.accounts}

            accounts = await HoyoAccount.filter(user_id=i.user.id).prefetch_related("user")
            if not accounts:
                raise NoAccountFoundError(list(Game))

            account = next((acc for acc in accounts if acc.current), accounts[0])
            return {"account": account, "accounts": accounts}

        msg = f"Unknown settings category: {self.category}"
        raise ValueError(msg)

    def _set_kwargs(self, **kwargs) -> None:
        if self.category is SettingsCategory.USER_SETTINGS:
            self.settings = kwargs["settings"]

        if self.category is SettingsCategory.ACCOUNT_SETTINGS:
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

        await i.edit_original_response(view=self)
