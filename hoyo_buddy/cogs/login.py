from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..db.models import HoyoAccount, User, get_locale
from ..ui.account.view import AccountManager

if TYPE_CHECKING:
    from ..bot.bot import HoyoBuddy, Interaction


class Login(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=locale_str("accounts", translate=False),
        description=locale_str("accounts_command_description"),
    )
    async def accounts(self, i: Interaction) -> Any:
        locale = await get_locale(i)
        user = await User.get(id=i.user.id)
        accounts = await HoyoAccount.filter(user=user).all()

        view = AccountManager(
            author=i.user,
            locale=locale,
            translator=i.client.translator,
            user=user,
            accounts=accounts,
        )
        await view.start(i)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Login(bot))
