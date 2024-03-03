from typing import TYPE_CHECKING, Any

from ...bot.translator import LocaleStr, Translator
from ...db.models import HoyoAccount, User
from ...embeds import DefaultEmbed
from ...emojis import (
    get_game_emoji,
)
from .. import Select, SelectOption, View
from .items.acc_select import AccountSelect
from .items.add_acc_btn import AddAccountButton
from .items.del_acc_btn import DeleteAccountButton
from .items.edit_nickname_btn import EditNicknameButton

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from ...bot.bot import INTERACTION


class AccountManager(View):
    def __init__(
        self,
        *,
        author: "discord.User | discord.Member",
        locale: "discord.Locale",
        translator: Translator,
        user: User,
        accounts: "Sequence[HoyoAccount]",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None

    async def init(self) -> None:
        if self.accounts:
            self.selected_account = self.accounts[0]
            self.add_item(AccountSelect(self.get_account_options()))
            self.add_item(AddAccountButton())
            self.add_item(EditNicknameButton())
            self.add_item(DeleteAccountButton())
        else:
            self.add_item(AddAccountButton())

    def get_account_embed(self) -> DefaultEmbed:
        account = self.selected_account

        if account is None:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Account Manager", key="account_manager_title"),
                description=LocaleStr(
                    "You don't have any accounts yet.",
                    key="account_manager_no_accounts_description",
                ),
            )
            return embed

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=str(account),
        )
        embed.add_field(
            name=LocaleStr("Game", key="account_game"),
            value=LocaleStr(account.game.value, warn_no_key=False),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Server", key="account_server"),
            value=LocaleStr(account.server, warn_no_key=False),
            inline=False,
        )
        if account.nickname:
            embed.add_field(
                name=LocaleStr("Username", key="account_username"),
                value=account.username,
                inline=False,
            )
        return embed

    def get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def refresh(self, i: "INTERACTION", *, soft: bool) -> Any:
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=self.user,
                accounts=accounts,
            )
            await view.init()
            await self.absolute_edit(i, embed=view.get_account_embed(), view=view)
            view.message = await i.original_response()
        else:
            account_selector = self.get_item("account_selector")
            if isinstance(account_selector, Select):
                account_selector.options = self.get_account_options()
            await self.absolute_edit(i, embed=self.get_account_embed(), view=self)
