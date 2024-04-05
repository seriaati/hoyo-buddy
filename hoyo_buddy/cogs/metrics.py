import logging
from typing import TYPE_CHECKING

import sentry_sdk.metrics
from discord import InteractionType, app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from discord import Guild

    from ..bot.bot import INTERACTION, HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class Metrics(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, _: "Guild") -> None:
        sentry_sdk.metrics.incr("guilds.joined")

    @commands.Cog.listener()
    async def on_guild_remove(self, _: "Guild") -> None:
        sentry_sdk.metrics.incr("guilds.joined", value=-1)

    @commands.Cog.listener()
    async def on_interaction(self, i: "INTERACTION") -> None:
        match i.type:
            case InteractionType.application_command:
                if isinstance(i.command, app_commands.Command):
                    if i.command.parent is None:
                        LOGGER_.info("[Command][%s] %s", i.user.id, i.command.name)
                        sentry_sdk.metrics.incr(
                            "commands.executed", tags={"command": i.command.name}
                        )
                    else:
                        LOGGER_.info(
                            "[Command][%s] %s %s", i.user.id, i.command.parent.name, i.command.name
                        )
                        sentry_sdk.metrics.incr(
                            "commands.executed",
                            tags={"command": f"{i.command.parent.name} {i.command.name}"},
                        )
                elif isinstance(i.command, app_commands.ContextMenu):
                    sentry_sdk.metrics.incr(
                        "context_menu_commands.executed",
                        tags={"command": i.command.name},
                    )
            case InteractionType.component:
                sentry_sdk.metrics.incr("components.interacted")
            case InteractionType.modal_submit:
                sentry_sdk.metrics.incr("modals.submitted")


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Metrics(bot))
