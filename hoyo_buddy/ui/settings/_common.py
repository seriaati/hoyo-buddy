from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy import ui
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class AccountToggleButton(ui.EmojiToggleButton["SettingsView"]):
    def __init__(self, *, attr: str, current: bool, **kwargs) -> None:
        self.attr = attr
        super().__init__(current=current, **kwargs)

    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        if "notif_settings." in self.attr:
            notif_attr = self.attr.split(".", 1)[1]
            setattr(self.view.account.notif_settings, notif_attr, self.current)
            await self.view.account.notif_settings.save(update_fields=(notif_attr,))
        else:
            setattr(self.view.account, self.attr, self.current)
            await self.view.account.save(update_fields=(self.attr,))

        await i.response.edit_message(view=self.view)


class AccountSelect(ui.Select["SettingsView"]):
    def __init__(self, *, current: HoyoAccount, accounts: list[HoyoAccount]) -> None:
        options = [
            ui.SelectOption(
                label=str(account),
                value=str(account.id),
                emoji=get_game_emoji(account.game),
                default=current.id == account.id,
            )
            for account in accounts
        ]

        super().__init__(
            custom_id="account_select",
            placeholder=LocaleStr(key="account_select_placeholder"),
            options=options,
        )
        self.accounts = accounts

    async def callback(self, i: Interaction) -> None:
        account = next((acc for acc in self.accounts if str(acc.id) == self.values[0]), None)
        assert account is not None
        self.view.account = account
        await self.view.update(i)
