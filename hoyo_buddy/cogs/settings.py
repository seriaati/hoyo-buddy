from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..db.models import Settings as UserSettings
from ..ui.settings import SettingsUI

if TYPE_CHECKING:
    from ..bot.bot import HoyoBuddy, Interaction


class Settings(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @app_commands.command(
        name=locale_str("settings"),
        description=locale_str("Configure your user settings", key="settings_command_description"),
    )
    async def settings_command(self, i: Interaction) -> Any:
        settings = await UserSettings.get(user_id=i.user.id)
        view = SettingsUI(
            author=i.user,
            locale=settings.locale or i.locale,
            translator=self.bot.translator,
            settings=settings,
        )
        await i.response.send_message(
            embed=view.get_embed(), file=view.get_brand_image_file(i.locale), view=view
        )
        view.message = await i.original_response()


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Settings(bot))
