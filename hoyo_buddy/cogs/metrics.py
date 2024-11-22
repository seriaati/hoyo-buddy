from __future__ import annotations

from typing import TYPE_CHECKING

from discord import InteractionType, app_commands
from discord.ext import commands
from loguru import logger

from hoyo_buddy.db.models import CommandMetric

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction


class Metrics(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, i: Interaction) -> None:
        match i.type:
            case InteractionType.application_command:
                if isinstance(i.command, app_commands.Command):
                    parameters = i.namespace.__dict__
                    guild_str = f"[{i.guild.id}]" if i.guild else ""
                    if i.command.parent is None:
                        logger.info(
                            f"[Command]{guild_str}[{i.user.id}] {i.command.name}",
                            parameters=parameters,
                        )
                        await CommandMetric.increment(i.command.name)
                    else:
                        logger.info(
                            f"[Command]{guild_str}[{i.user.id}] {i.command.parent.name} {i.command.name}",
                            parameters=parameters,
                        )
                        await CommandMetric.increment(f"{i.command.parent.name} {i.command.name}")
                elif isinstance(i.command, app_commands.ContextMenu):
                    await CommandMetric.increment(i.command.name)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Metrics(bot))
