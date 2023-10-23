from typing import Literal

from discord import InteractionResponded, app_commands
from discord.app_commands.errors import AppCommandError
from discord.interactions import Interaction

from ..db.models import Settings, User
from ..ui.embeds import ErrorEmbed
from . import HoyoBuddy


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: Interaction) -> Literal[True]:
        user, created = await User.get_or_create(id=i.user.id)
        if created:
            await Settings.create(user=user)
        return True

    async def on_error(self, i: Interaction[HoyoBuddy], error: AppCommandError) -> None:
        embed = ErrorEmbed(title="An error occurred", description=str(error))
        user = await User.get(id=i.user.id).prefetch_related("settings")
        locale = user.settings.locale or i.locale
        await embed.translate(locale, i.client.translator)
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
