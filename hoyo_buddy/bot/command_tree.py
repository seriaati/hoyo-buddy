import logging
from typing import Literal

from discord import InteractionResponded, app_commands
from discord.interactions import Interaction

from ..db.models import Settings, User
from ..ui.embeds import get_error_embed
from . import HoyoBuddy

log = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: Interaction) -> Literal[True]:
        user, created = await User.get_or_create(id=i.user.id)
        if created:
            await Settings.create(user=user)
        return True

    async def on_error(self, i: Interaction[HoyoBuddy], error: Exception) -> None:
        log.exception(error)
        embed = await get_error_embed(i, error)
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
