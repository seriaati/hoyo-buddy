import logging
from typing import Literal

from discord import InteractionResponded, app_commands

from ..db import Settings, User
from .bot import INTERACTION
from .error_handler import get_error_embed

__all__ = ("CommandTree",)

log = logging.getLogger(__name__)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: INTERACTION) -> Literal[True]:
        user, created = await User.get_or_create(id=i.user.id)
        if created:
            await Settings.create(i.client.redis_pool, user=user)
        return True

    async def on_error(self, i: INTERACTION, e: app_commands.AppCommandError) -> None:
        error = e.original if isinstance(e, app_commands.errors.CommandInvokeError) else e
        locale = await Settings.get_locale(i.user.id, i.client.redis_pool) or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(e)

        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
