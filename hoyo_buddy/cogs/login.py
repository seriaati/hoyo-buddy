from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..db.models import HoyoAccount, Settings, User
from ..ui.account.view import AccountManager

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy


class Login(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    @app_commands.command(
        name=locale_str("accounts", translate=False),
        description=locale_str("Manage your accounts", key="accounts_command_description"),
    )
    async def accounts(self, i: "INTERACTION") -> Any:
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        user = await User.get(id=i.user.id)
        accounts = await HoyoAccount.filter(user=user).all()

        view = AccountManager(
            author=i.user,
            locale=locale,
            translator=i.client.translator,
            user=user,
            accounts=accounts,
        )
        await view.init()

        embed = view.get_account_embed()
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Login(bot))
