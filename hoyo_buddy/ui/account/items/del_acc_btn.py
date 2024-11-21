from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import DELETE, FORWARD
from hoyo_buddy.l10n import LocaleStr

from ...components import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class DeleteAccountContinue(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account_continue",
            label=LocaleStr(key="continue_button_label"),
            emoji=FORWARD,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        await self.view.refresh(i, soft=False)


class DeleteAccountButton(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account",
            style=ButtonStyle.red,
            emoji=DELETE,
            label=LocaleStr(key="delete_account_button_label"),
            row=3,
        )

    async def callback(self, i: Interaction) -> None:
        account = self.view.selected_account
        assert account is not None
        await account.delete()

        new_account = await HoyoAccount.filter(user=self.view.user).first()
        if new_account is not None:
            new_account.current = True
            await new_account.save(update_fields=("current",))

        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="account_deleted_title"),
            description=LocaleStr(key="account_deleted_description", account=str(account)),
        )
        self.view.clear_items()
        self.view.add_item(DeleteAccountContinue())
        await i.response.edit_message(embed=embed, view=self.view)
