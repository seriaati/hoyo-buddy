from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import DELETE, FORWARD

from ....db.models import HoyoAccount
from ...components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import AccountManager  # noqa: F401


class DeleteAccountContinue(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account_continue",
            label=LocaleStr("Continue", key="continue_button_label"),
            emoji=FORWARD,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: INTERACTION) -> None:
        await self.view.refresh(i, soft=False)


class DeleteAccountButton(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account",
            style=ButtonStyle.red,
            emoji=DELETE,
            label=LocaleStr("Delete selected account", key="delete_account_button_label"),
            row=3,
        )

    async def callback(self, i: INTERACTION) -> None:
        account = self.view.selected_account
        assert account is not None
        await account.delete()

        new_account = await HoyoAccount.filter(user=self.view.user).first()
        if new_account is not None:
            new_account.current = True
            await new_account.save(update_fields=("current",))

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Account Deleted", key="account_deleted_title"),
            description=LocaleStr(
                "{account} has been deleted.",
                key="account_deleted_description",
                account=str(account),
            ),
        )
        self.view.clear_items()
        self.view.add_item(DeleteAccountContinue())
        await i.response.edit_message(embed=embed, view=self.view)
