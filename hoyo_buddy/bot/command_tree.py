import logging
from typing import Literal

from discord import InteractionResponded, app_commands
from discord.interactions import Interaction

from ..db.models import Settings, User
from ..exceptions import HoyoBuddyError
from ..ui.embeds import ErrorEmbed
from . import HoyoBuddy

log = logging.getLogger(__name__)


async def get_error_embed(i: Interaction[HoyoBuddy], error: Exception) -> ErrorEmbed:
    user = await User.get(id=i.user.id).prefetch_related("settings")

    if isinstance(error, HoyoBuddyError):
        embed = ErrorEmbed(
            user.settings.locale or i.locale,
            i.client.translator,
            title="An error occurred",
            description=str(error),
            **error.kwargs,
        )
    else:
        embed = ErrorEmbed(
            user.settings.locale or i.locale,
            i.client.translator,
            title="An error occurred",
            description=str(error),
        )
    return embed


class CommandTree(app_commands.CommandTree):
    async def interaction_check(
        self, i: Interaction
    ) -> Literal[True]:  # skipcq: PYL-W0221
        user, created = await User.get_or_create(id=i.user.id)
        if created:
            await Settings.create(user=user)
        return True

    async def on_error(
        self, i: Interaction[HoyoBuddy], error: Exception
    ) -> None:  # skipcq: PYL-W0221
        log.exception(error)
        embed = await get_error_embed(i, error)
        try:
            await i.response.send_message(embed=embed, ephemeral=True)
        except InteractionResponded:
            await i.followup.send(embed=embed, ephemeral=True)
