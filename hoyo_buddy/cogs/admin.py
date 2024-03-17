import asyncio
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, ui
from discord.ext import commands
from seria.utils import write_json

from ..constants import UID_STARTS
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
        await i.response.send_message("Farm check tasks started.")
        for uid_start in UID_STARTS:
            asyncio.create_task(FarmChecker.execute(i.client, uid_start))


class Admin(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    async def cog_check(self, ctx: "Context") -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="sync")
    async def sync_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Syncing commands...")
        synced_commands = await self.bot.tree.sync()
        await write_json(
            "hoyo_buddy/bot/data/synced_commands.json", {c.name: c.id for c in synced_commands}
        )
        await self.bot.translator.load_synced_commands_json()
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

    @commands.command(name="run-tasks", aliases=["rt"])
    async def run_tasks_command(self, ctx: commands.Context) -> Any:
        view = TaskView()
        await ctx.send("Select a task to run.", view=view)

    @commands.command(name="not-translated", aliases=["nt"])
    async def not_translated_command(self, ctx: commands.Context) -> Any:
        not_translated = self.bot.translator._not_translated
        await ctx.send(f"Not translated:\n```\n{not_translated}\n```\nTotal: {len(not_translated)}")

    @commands.command(name="update-assets", aliases=["ua"])
    async def update_assets_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Updating assets...")
        await self.bot.update_assets()
        await message.edit(content="Updated assets.")


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Admin(bot))
