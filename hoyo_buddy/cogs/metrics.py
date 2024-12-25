from __future__ import annotations

from typing import TYPE_CHECKING

from discord import InteractionType, app_commands
from discord.ext import commands
from loguru import logger

from hoyo_buddy.db import CommandMetric

if TYPE_CHECKING:
    from ..bot import HoyoBuddy
    from ..types import Interaction


class Metrics(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    def _get_command_name(self, command: app_commands.Command) -> str:
        if command.parent is not None:
            if command.parent.parent is not None:
                return f"{command.parent.parent.name} {command.parent.name} {command.name}"
            return f"{command.parent.name} {command.name}"
        return command.name

    @commands.Cog.listener()
    async def on_interaction(self, i: Interaction) -> None:
        if i.type is InteractionType.application_command:
            if isinstance(i.command, app_commands.Command):
                parameters = i.namespace.__dict__
                command_name = self._get_command_name(i.command)
                logger.info(f"[Command][{i.user.id}] {command_name}", parameters=parameters)
                await CommandMetric.increment(command_name)
            elif isinstance(i.command, app_commands.ContextMenu):
                await CommandMetric.increment(i.command.name)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Metrics(bot))
