from typing import Any

import discord
from discord import app_commands
from discord.app_commands import locale_str as _T
from discord.ext import commands

from ..bot import HoyoBuddy
from ..db.models import User
from ..ui.login.accounts import AccountManager


class Login(commands.Cog):
    def __init__(self, bot: HoyoBuddy):
        self.bot = bot

    @app_commands.command(
        name=_T("accounts", no_trans=True), description=_T("Manage your accounts")
    )
    async def accounts(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        user = await User.get(id=i.user.id).prefetch_related("accounts", "settings")
        locale = user.settings.locale or i.locale
        view = AccountManager(
            author=i.user,
            locale=locale,
            translator=i.client.translator,
            user=user,
            accounts=await user.accounts.all(),
        )
        await view.start()
        embed = view.get_account_embed()
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()


async def setup(bot: HoyoBuddy):
    await bot.add_cog(Login(bot))
