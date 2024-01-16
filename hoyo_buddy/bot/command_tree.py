from typing import TYPE_CHECKING, Literal

from discord import InteractionResponded, app_commands

from ..db import Settings, User
from .error_handler import get_error_embed

if TYPE_CHECKING:
    from .bot import INTERACTION

__all__ = ("CommandTree",)


class CommandTree(app_commands.CommandTree):
    async def interaction_check(self, i: "INTERACTION") -> Literal[True]:
        user = await User.silent_create(id=i.user.id)
        if user:
            await Settings.create(user=user)
        return True

    async def on_error(self, i: "INTERACTION", e: app_commands.AppCommandError) -> None:
        error = e.original if isinstance(e, app_commands.errors.CommandInvokeError) else e
        locale = (await Settings.get(user_id=i.user.id)).locale or i.locale
        embed, recognized = get_error_embed(error, locale, i.client.translator)
        if not recognized:
            i.client.capture_exception(e)

        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
