from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.ui.reminders.view import RemindersView

from ..types import Interaction

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Reminders(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=locale_str("reminders"), description=COMMANDS["reminders"].description
    )
    async def reminders_command(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=True)

        view = RemindersView(author=i.user, locale=await get_locale(i))
        await view.update(i)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Reminders(bot))
