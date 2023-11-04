from typing import Any, List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from ..bot import HoyoBuddy, Translator
from ..bot import locale_str as _T
from ..db import HoyoAccount, Settings, User
from ..ui.hoyo.checkin import CheckInUI


class Hoyo(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
        self.bot = bot

    @staticmethod
    async def _account_autocomplete(
        user_id: int, current: str, locale: discord.Locale, translator: Translator
    ) -> List[discord.app_commands.Choice]:
        accounts = await HoyoAccount.filter(user__id=user_id).all()
        if not accounts:
            return [
                discord.app_commands.Choice(
                    name=discord.app_commands.locale_str(
                        "You don't have any accounts yet. Add one with /accounts",
                        key="no_accounts_autocomplete_choice",
                    ),
                    value="none",
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account} | {translator.translate(_T(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current in str(account)
        ]

    @staticmethod
    async def _no_account_response(i, locale):
        return await i.response.send_message(
            i.client.translator.translate(
                _T(
                    "You don't have any accounts yet. Add one with </accounts>",
                    key="no_accounts_autocomplete_selected",
                ),
                locale,
            ),
            ephemeral=True,
        )

    @staticmethod
    async def _get_user(user_id: int) -> User:
        return await User.get(id=user_id).prefetch_related("settings")

    @staticmethod
    def _get_locale(user: User, interaction_locale: discord.Locale) -> discord.Locale:
        return user.settings.locale or interaction_locale

    async def _get_first_account(
        self, user: User, i: discord.Interaction, locale: discord.Locale
    ) -> Optional[HoyoAccount]:
        accounts = await user.accounts.all()
        if not accounts:
            await self._no_account_response(i, locale)
        else:
            return accounts[0]

    @staticmethod
    async def _get_specific_account(account_value: str, user: User) -> HoyoAccount:
        uid, game = account_value.split("_")
        account = await user.accounts.filter(uid=uid, game=game).first()
        if account is None:
            raise AssertionError("Account not found")
        return account

    async def _get_account(
        self,
        user: User,
        account_value: Optional[str],
        i: discord.Interaction,
        locale: discord.Locale,
    ) -> Optional[HoyoAccount]:
        if account_value is None:
            return await self._get_first_account(user, i, locale)
        elif account_value == "none":
            await self._no_account_response(i, locale)
        else:
            return await self._get_specific_account(account_value, user)

    @app_commands.command(
        name=app_commands.locale_str("check-in", translate=False),
        description=app_commands.locale_str(
            "Game daily check-in", key="checkin_command_description"
        ),
    )
    @app_commands.rename(
        acc_value=app_commands.locale_str(
            "account", key="account_autocomplete_param_name"
        )
    )
    @app_commands.describe(
        acc_value=app_commands.locale_str(
            "Account to run this command with, defaults to the first one",
            key="account_autocomplete_param_description",
        )
    )
    async def checkin_command(
        self, i: discord.Interaction[HoyoBuddy], acc_value: Optional[str] = None
    ) -> Any:
        user = await self._get_user(i.user.id)
        locale = self._get_locale(user, i.locale)
        account = await self._get_account(user, acc_value, i, locale)
        if account is None:
            return

        dark_mode = user.settings.dark_mode
        view = CheckInUI(
            account,
            dark_mode=dark_mode,
            author=i.user,
            locale=locale,
            translator=self.bot.translator,
        )
        await view.start(i)

    @checkin_command.autocomplete("acc_value")
    async def check_in_command_autocomplete(
        self, i: discord.Interaction, current: str
    ) -> List[app_commands.Choice]:
        locale = (await Settings.get(user__id=i.user.id)).locale or i.locale
        return await self._account_autocomplete(
            i.user.id, current, locale, self.bot.translator
        )


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Hoyo(bot))
