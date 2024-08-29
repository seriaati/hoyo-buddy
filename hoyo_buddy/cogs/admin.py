from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, TextStyle, ui
from discord.ext import commands
from genshin import Game
from seria.utils import write_json

from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.emojis import get_game_emoji

from ..constants import UID_STARTS
from ..hoyo.auto_tasks.auto_redeem import AutoRedeem
from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker
from .search import Search

if TYPE_CHECKING:
    from discord.ext.commands.context import Context

    from ..bot import HoyoBuddy
    from ..types import Interaction


class DMModal(ui.Modal):
    user_ids = ui.TextInput(label="User IDs")
    message = ui.TextInput(label="Message", style=TextStyle.paragraph)

    async def on_submit(self, i: Interaction) -> None:
        await i.response.defer()
        self.stop()


class DMModalView(ui.View):
    def __init__(self) -> None:
        super().__init__()

    @ui.button(label="Open modal", style=ButtonStyle.blurple)
    async def send(self, i: Interaction, _: ui.Button) -> None:
        modal = DMModal(title="Set message", custom_id="dm_modal")
        await i.response.send_modal(modal)
        await modal.wait()

        user_ids = [int(user_id) for user_id in modal.user_ids.value.split(",")]

        await i.edit_original_response(content=f"Sending message to {len(user_ids)} users...")
        for user_id in user_ids:
            await i.client.dm_user(int(user_id), content=modal.message.value)
        await i.edit_original_response(content="Done.")


class TaskView(ui.View):
    def __init__(self) -> None:
        super().__init__()

    async def interaction_check(self, i: Interaction) -> bool:
        return await i.client.is_owner(i.user)

    @ui.button(label="Daily check-in", style=ButtonStyle.blurple)
    async def daily_checkin(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("Daily check-in task started.")
        asyncio.create_task(DailyCheckin.execute(i.client))

    @ui.button(label="Notes check", style=ButtonStyle.blurple)
    async def notes_check(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("Notes check task started.")
        asyncio.create_task(NotesChecker.execute(i.client))

    @ui.button(label="Farm check", style=ButtonStyle.blurple)
    async def farm_check(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("Farm check tasks started.")
        for uid_start in UID_STARTS:
            asyncio.create_task(FarmChecker.execute(i.client, uid_start))

    @ui.button(label="Auto redeem", style=ButtonStyle.blurple)
    async def auto_redeem(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("Auto redeem task started.")
        asyncio.create_task(AutoRedeem.execute(i.client))


class Admin(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self._tasks: set[asyncio.Task] = set()

    async def cog_check(self, ctx: Context) -> bool:
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

    @commands.command(name="fetch-source-strings", aliases=["fss"])
    async def fetch_source_strings_command(self, ctx: commands.Context) -> Any:
        await self.bot.translator.load_l10n_files()
        await ctx.send(content="Fetched source strings.")

    @commands.command(name="run-tasks", aliases=["rt"])
    async def run_tasks_command(self, ctx: commands.Context) -> Any:
        view = TaskView()
        await ctx.send("Select a task to run.", view=view)

    @commands.command(name="update-assets", aliases=["ua"])
    async def update_assets_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Updating assets...")
        await self.bot.update_assets()
        await message.edit(content="Updated assets.")

    @commands.command(name="update-search-autocomplete", aliases=["usa"])
    async def update_search_autocomplete_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Updating search autocomplete...")
        search_cog = self.bot.get_cog("Search")

        if isinstance(search_cog, Search):
            asyncio.create_task(search_cog._setup_search_autocomplete_choices())
        await message.edit(content="Search autocomplete update task started.")

    @commands.command(name="add-codes", aliases=["ac"])
    async def add_codes_command(self, ctx: commands.Context, game: Game, codes: str) -> Any:
        codes_: set[str] = set()
        for code in codes.split(","):
            code_ = code.split("/")[-1] if "https" in code else code
            codes_.add(code_)

        message = await ctx.send("Adding codes...")
        task_ran = await AutoRedeem.execute(self.bot, game, codes.split(","))
        if not task_ran:
            await message.edit(content="Auto redeem task is already running.")

    @commands.command(name="dm")
    async def dm_command(self, ctx: commands.Context) -> Any:
        view = DMModalView()
        await ctx.send(view=view)

    @commands.command(name="get-accounts", aliases=["ga"])
    async def get_accounts_command(self, ctx: commands.Context, user_id: int) -> Any:
        accounts = await HoyoAccount.filter(user_id=user_id).all()
        msg = "\n".join(
            [
                f"- [{account.id}] {get_game_emoji(account.game)} {account.uid}, {account.username}, {account.region}"
                for account in accounts
            ]
        )
        await ctx.send(msg)

    @commands.command(name="get-cookies", aliases=["gc"])
    async def get_cookies_command(self, ctx: commands.Context, account_id: int) -> Any:
        account = await HoyoAccount.get_or_none(id=account_id)
        if account is None:
            return await ctx.send("Account not found.")

        await ctx.send(f"cookies:\n```{account.cookies}```")
        if account.device_fp is not None:
            await ctx.send(f"device_fp:\n```{account.device_fp}```")
        if account.device_id is not None:
            await ctx.send(f"device_id:\n```{account.device_id}```")
        return None


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Admin(bot))
