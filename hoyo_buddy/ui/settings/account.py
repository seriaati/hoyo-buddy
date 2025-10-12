from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class PublicToggleButton(ui.EmojiToggleButton["SettingsView"]):
    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.account.public = self.current
        await self.view.account.save(update_fields=("public",))

        await i.response.edit_message(view=self.view)


class DailyCheckinToggleButton(ui.EmojiToggleButton["SettingsView"]):
    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.account.daily_checkin = self.current
        await self.view.account.save(update_fields=("daily_checkin",))

        await i.response.edit_message(view=self.view)


class RedeemCodeToggleButton(ui.EmojiToggleButton["SettingsView"]):
    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.account.auto_redeem = self.current
        await self.view.account.save(update_fields=("auto_redeem",))

        await i.response.edit_message(view=self.view)


class AccountSelect(ui.Select["SettingsView"]):
    def __init__(self, accounts: list[HoyoAccount]) -> None:
        options = [
            ui.SelectOption(
                label=str(account),
                value=str(account.id),
                emoji=get_game_emoji(account.game),
                default=account.current,
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

        # 'current' is already saved here
        await account.user.set_acc_as_current(account)

        # this is for updating the dropdown default selection
        for acc in self.view.accounts:
            acc.current = acc.id == account.id

        await self.view.update(i)


class AccountSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, account: HoyoAccount, accounts: list[HoyoAccount]) -> None:
        super().__init__(
            ui.TextDisplay(
                content=LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="account_settings_title"),
                    desc=LocaleStr(key="account_settings_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(content=LocaleStr(key="public_account_desc")),
                accessory=PublicToggleButton(current=account.public),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(content=LocaleStr(key="daily_checkin_desc")),
                accessory=DailyCheckinToggleButton(current=account.daily_checkin),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(content=LocaleStr(key="redeem_code_desc")),
                accessory=RedeemCodeToggleButton(
                    current=account.auto_redeem, disabled=not account.can_redeem_code
                ),
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(AccountSelect(accounts)),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
        )
