import asyncio
from typing import TYPE_CHECKING, Any

import aiofiles
import orjson
from discord import ButtonStyle, ui
from discord.ext import commands

from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker

if TYPE_CHECKING:
    from discord.ext.commands.context import Context

    from ..bot.bot import INTERACTION, HoyoBuddy


class TaskView(ui.View):
    async def interaction_check(self, i: "INTERACTION") -> bool:
        return await i.client.is_owner(i.user)

    @ui.button(label="Daily Check-in", style=ButtonStyle.blurple)
    async def daily_checkin(self, i: "INTERACTION", _: ui.Button) -> None:
        await i.response.send_message("Daily check-in task started.")
        asyncio.create_task(DailyCheckin.execute(i.client))

    @ui.button(label="Notes Check", style=ButtonStyle.blurple)
    async def notes_check(self, i: "INTERACTION", _: ui.Button) -> None:
        await i.response.send_message("Notes check task started.")
        asyncio.create_task(NotesChecker.execute(i.client))

    @ui.button(label="Farm Check", style=ButtonStyle.blurple)
    async def farm_check(self, i: "INTERACTION", _: ui.Button) -> None:
        await i.response.send_message("Farm check task for uid_start `9` started.")
        asyncio.create_task(FarmChecker.execute(i.client, "9"))


class Admin(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    async def cog_check(self, ctx: "Context") -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="sync")
    async def sync_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Syncing commands...")
        synced_commands = await self.bot.tree.sync()
        async with aiofiles.open("hoyo_buddy/bot/data/synced_commands.json", "w") as f:
            await f.write(orjson.dumps({c.name: c.id for c in synced_commands}).decode())
        await message.edit(content=f"Synced {len(synced_commands)} commands.")

    @commands.command(name="push-source-strings", aliases=["pss"])
    async def push_source_strings_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Pushing source strings...")
        await self.bot.translator.push_source_strings()
        await message.edit(content="Pushed source strings.")

    @commands.command(name="fetch-source-strings", aliases=["fss"])
    async def fetch_source_strings_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Fetching source strings...")
        await self.bot.translator.fetch_source_strings()
        await message.edit(content="Fetched source strings.")

    @commands.command(name="reload-synced-commands", aliases=["rsc"])
    async def reload_sync_commands_command(self, ctx: commands.Context) -> Any:
        await self.bot.translator.load_synced_commands_json()
        await ctx.send("Reloaded synced commands JSON.")

    @commands.command(name="run-tasks", aliases=["rt"])
    async def run_tasks_command(self, ctx: commands.Context) -> Any:
        view = TaskView()
        await ctx.send("Select a task to run.", view=view)


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Admin(bot))
