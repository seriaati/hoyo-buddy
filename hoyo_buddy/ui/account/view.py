from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord.utils import format_dt

from hoyo_buddy.constants import AUTO_TASK_FEATURE_KEYS
from hoyo_buddy.db import AutoTaskResult, HoyoAccount, get_dyk
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import CHECK, get_game_emoji
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.ui import View

from .. import SelectOption
from .items.acc_select import AccountSelect
from .items.add_acc_btn import AddAccountButton
from .items.del_acc_btn import DeleteAccountButton
from .items.edit_nickname_btn import EditNicknameButton

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from hoyo_buddy.db import User
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import AutoTaskType, Interaction


class AccountManager(View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member | None,
        locale: Locale,
        user: User,
        accounts: Sequence[HoyoAccount],
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None
        self.task_results: list[AutoTaskResult] = []

    @property
    def _acc_embed(self) -> DefaultEmbed:
        account = self.selected_account

        if account is None:
            return DefaultEmbed(
                self.locale,
                title=LocaleStr(key="account_manager_title"),
                description=LocaleStr(key="account_manager_no_accounts_description"),
            )

        embed = DefaultEmbed(self.locale, title=str(account))
        embed.add_field(
            name=LocaleStr(key="search_command_game_param_name"), value=EnumStr(account.game)
        )
        if account.nickname:
            embed.add_field(name=LocaleStr(key="account_username"), value=account.username)
        if self.task_results:
            lines = [
                f"{self._get_task_label(result.task_type)}: "
                f"{CHECK if result.success else '❌'} {format_dt(result.completed_at, 'R')}"
                for result in self.task_results
            ]
            embed.add_field(
                name=LocaleStr(key="auto_task_status_field_name"),
                value="\n".join(lines),
                inline=False,
            )
        embed.set_footer(text=LocaleStr(key="account_manager_footer"))
        return embed

    def _get_task_label(self, task_type: AutoTaskType) -> str:
        feature_key = AUTO_TASK_FEATURE_KEYS.get(task_type)
        if feature_key is None:
            return task_type

        if "mimo" in task_type:
            return LocaleStr(
                custom_str="{mimo_title} {label}",
                mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                label=LocaleStr(key=feature_key),
            ).translate(self.locale)
        return LocaleStr(key=feature_key).translate(self.locale)

    async def _fetch_task_results(self) -> None:
        if self.selected_account is None:
            self.task_results = []
        else:
            self.task_results = await AutoTaskResult.filter(
                account_id=self.selected_account.id
            ).order_by("task_type")

    def _add_items(self) -> None:
        if self.accounts:
            self.selected_account = (
                next((a for a in self.accounts if a.current), None) or self.accounts[0]
            )
            self.add_item(AccountSelect(self._get_account_options()))
            self.add_item(AddAccountButton())
            self.add_item(EditNicknameButton())
            self.add_item(DeleteAccountButton())
        else:
            self.add_item(AddAccountButton())

    def _get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def start(self, i: Interaction) -> None:
        self._add_items()
        await self._fetch_task_results()
        embed = self._acc_embed
        await i.response.defer(ephemeral=True)
        self.message = await i.edit_original_response(
            embed=embed, view=self, content=await get_dyk(i)
        )

    async def refresh(self, i: Interaction, *, soft: bool) -> Any:
        """Refresh the account manager view.

        Args:
            i: The interaction object.
            soft: Whether to refetch account data from the database.
        """
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author, locale=self.locale, user=self.user, accounts=accounts
            )
            await view.start(i)
        else:
            await self._fetch_task_results()
            await self.absolute_edit(i, embed=self._acc_embed, view=self)
