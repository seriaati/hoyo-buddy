import logging
from typing import Literal

from discord import InteractionResponded, app_commands
from discord.interactions import Interaction

from ..db import Settings, User
from .bot import HoyoBuddy
from .error_handler import get_error_embed

__all__ = ("CommandTree",)

log = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: Interaction) -> Literal[True]:
        user, created = await User.get_or_create(id=i.user.id)
        if created:
            await Settings.create(user=user)
        return True

    async def on_error(self, i: Interaction[HoyoBuddy], error: Exception) -> None:
        i.client.capture_exception(error)

        user = await User.get(id=i.user.id).prefetch_related("settings")
        locale = user.settings.locale or i.locale
        embed = get_error_embed(error, locale, i.client.translator)
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
