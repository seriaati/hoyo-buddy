from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.db import Settings as UserSettings
from hoyo_buddy.db.utils import get_locale, show_anniversary_dismissible

from ..types import Interaction
from ..ui.ssettings import SettingsUI

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Settings(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(name=locale_str("settings"), description=COMMANDS["settings"].description)
    async def settings_command(self, i: Interaction) -> Any:
        await i.response.defer(ephemeral=True)

        settings = await UserSettings.get(user_id=i.user.id)
        locale = await get_locale(i)
        view = SettingsUI(author=i.user, locale=locale, settings=settings)
        await i.followup.send(
            embed=view.get_embed(), file=view.get_brand_image_file(locale), view=view
        )
        view.message = await i.original_response()

        await show_anniversary_dismissible(i)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Settings(bot))
