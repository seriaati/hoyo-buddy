from __future__ import annotations

from typing import TYPE_CHECKING

from discord.utils import get as dget

from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class AccountSelect(PaginatorSelect[AccountManager]):
    def __init__(self, options: list[SelectOption]) -> None:
        super().__init__(
            custom_id="account_selector",
            options=options,
            placeholder=LocaleStr(key="account_select_placeholder"),
        )

    async def callback(self, i: Interaction) -> None:
        uid, game = self.values[0].split("_")
        selected_account = dget(self.view.accounts, uid=int(uid), game__value=game)
        assert selected_account is not None

        await self.view.user.set_acc_as_current(selected_account)
        self.view.selected_account = selected_account
        self.update_options_defaults()
        await self.view.refresh(i, soft=True)
