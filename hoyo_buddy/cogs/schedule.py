from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any

import discord
from discord import ui
from discord.ext import commands, tasks
from loguru import logger
from seria.utils import create_bullet_list

from hoyo_buddy.config import Deployment
from hoyo_buddy.db.models.json_file import JSONFile
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimoBuy, AutoMimoDraw, AutoMimoTask
from hoyo_buddy.hoyo.auto_tasks.embed_sender import EmbedSender
from hoyo_buddy.hoyo.auto_tasks.web_events_notify import WebEventsNotify

from ..constants import (
    CODE_CHANNEL_IDS,
    GI_UID_PREFIXES,
    HB_GAME_TO_GPY_GAME,
    SUPPORTER_ROLE_ID,
    UTC_8,
)
from ..hoyo.auto_tasks.auto_redeem import AutoRedeem
from ..hoyo.auto_tasks.daily_checkin import DailyCheckin
from ..hoyo.auto_tasks.farm_check import FarmChecker
from ..hoyo.auto_tasks.notes_check import NotesChecker
from ..utils import convert_code_to_redeem_url, get_now

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..bot import HoyoBuddy


class RunTaskButton(ui.Button):
    def __init__(self, task_cls: Any) -> None:
        super().__init__(label=task_cls.__name__)
        self.task_cls = task_cls

    async def callback(self, i: Interaction) -> None:
        await i.response.send_message(f"{self.task_cls.__name__} task started")
        asyncio.create_task(self.task_cls.execute(i.client))


class RunTaskView(ui.View):
    def __init__(self) -> None:
        super().__init__()
        tasks = (
            DailyCheckin,
            NotesChecker,
            AutoRedeem,
            AutoMimoTask,
            AutoMimoBuy,
            AutoMimoDraw,
            WebEventsNotify,
            EmbedSender,
        )
        for task in tasks:
            self.add_item(RunTaskButton(task))

    async def interaction_check(self, i: Interaction) -> bool:
        return await i.client.is_owner(i.user)

    @ui.button(label="FarmChecker")
    async def farm_check(self, i: Interaction, _: ui.Button) -> None:
        await i.response.send_message("FarmChecker task started")
        for uid_start in GI_UID_PREFIXES:
            asyncio.create_task(FarmChecker(i.client).execute(uid_start))


class Schedule(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if not self.bot.config.schedule:
            return

        if self.bot.config.deployment == "main":
            self.run_send_embeds.start()
            self.run_farm_checks.start()
            self.run_notes_check.start()
            self.run_web_events_notify.start()
            self.send_codes_to_channels.start()
            self.update_supporter_ids.start()

        self.update_assets.start()

    async def cog_unload(self) -> None:
        if not self.bot.config.schedule:
            return

        if self.bot.config.deployment == "main":
            self.run_send_embeds.cancel()
            self.run_farm_checks.cancel()
            self.run_notes_check.cancel()
            self.run_web_events_notify.cancel()
            self.send_codes_to_channels.cancel()
            self.update_supporter_ids.cancel()

        self.update_assets.cancel()

    @commands.is_owner()
    @commands.command(name="run-task", aliases=["rt"])
    async def run_task(self, ctx: commands.Context, deployment: Deployment) -> None:
        if deployment != self.bot.deployment:
            return

        await ctx.send("Select a task to run", view=RunTaskView())

    @tasks.loop(time=[datetime.time(hour, 0, 0, tzinfo=UTC_8) for hour in (4, 11, 17)])
    async def run_farm_checks(self) -> None:
        self.bot.farm_check_running = True
        hour = get_now().hour

        if hour == 11:
            await FarmChecker(self.bot).execute("7")
        elif hour == 17:
            await FarmChecker(self.bot).execute("6")
        else:
            for uid_start in GI_UID_PREFIXES:
                if uid_start in {"7", "6"}:
                    continue
                await FarmChecker(self.bot).execute(uid_start)

        self.bot.farm_check_running = False

    @tasks.loop(time=datetime.time(11, 0, 0, tzinfo=UTC_8))
    async def update_assets(self) -> None:
        await self.bot.update_assets()

    @tasks.loop(minutes=1)
    async def run_notes_check(self) -> None:
        await NotesChecker.execute(self.bot)

    @tasks.loop(minutes=1)
    async def run_send_embeds(self) -> None:
        await EmbedSender.execute(self.bot)

    @tasks.loop(time=[datetime.time(hour, 0, 0, tzinfo=UTC_8) for hour in range(0, 24, 1)])
    async def run_web_events_notify(self) -> None:
        await WebEventsNotify.execute(self.bot)

    @tasks.loop(minutes=30)
    async def send_codes_to_channels(self) -> None:
        if self.bot.config.is_dev:
            return

        guild = await self.bot.get_or_fetch_guild()
        if guild is None:
            logger.warning("Cannot get guild, skipping code sending")
            return

        sent_codes: dict[str, list[str]] = await JSONFile.read("sent_codes.json", default={})
        game_codes = await AutoRedeem.get_codes(self.bot.session)

        for game, codes in game_codes.items():
            if game not in CODE_CHANNEL_IDS:
                continue

            channel = guild.get_channel(CODE_CHANNEL_IDS[game])
            if not isinstance(channel, discord.TextChannel):
                continue

            game_sent_codes = set(sent_codes.get(HB_GAME_TO_GPY_GAME[game].value, []))
            codes_to_send = [c for c in codes if c not in game_sent_codes]

            if codes_to_send:
                codes_to_send_formatted = [
                    convert_code_to_redeem_url(code, game=game) for code in codes_to_send
                ]
                try:
                    message = await channel.send(create_bullet_list(codes_to_send_formatted))
                except Exception as e:
                    self.bot.capture_exception(e)
                    continue
                await message.publish()

            game_sent_codes.update(codes_to_send)
            sent_codes[HB_GAME_TO_GPY_GAME[game].value] = list(game_sent_codes)

        await JSONFile.write("sent_codes.json", sent_codes)

    @commands.is_owner()
    @commands.command(name="send-codes", aliases=["sc"])
    async def send_codes(self, ctx: commands.Context, deployment: Deployment) -> None:
        """Send codes to the configured channels."""
        if deployment != self.bot.deployment:
            return

        message = await ctx.send("Sending codes to channels...")
        await self.send_codes_to_channels()
        await message.edit(content="Codes sent.")

    @tasks.loop(hours=1)
    async def update_supporter_ids(self) -> None:
        guild = await self.bot.get_or_fetch_guild()
        if guild is None:
            return

        if not guild.chunked:
            await guild.chunk()

        role_id = SUPPORTER_ROLE_ID
        supporter_role = discord.utils.get(guild.roles, id=role_id)
        if supporter_role is None:
            logger.error(f"Failed to find supporter role with ID {role_id}")
            return

        supporter_ids = [member.id for member in supporter_role.members]
        await JSONFile.write("supporter_ids.json", supporter_ids)

    @commands.is_owner()
    @commands.command(name="update-supporter-ids", aliases=["usi"])
    async def update_supporter_ids_command(
        self, ctx: commands.Context, deployment: Deployment
    ) -> None:
        """Update the supporter IDs from the configured guild."""
        if deployment != self.bot.deployment:
            return

        message = await ctx.send("Updating supporter IDs...")
        await self.update_supporter_ids()
        await message.edit(content="Supporter IDs updated.")

    @run_farm_checks.before_loop
    @update_assets.before_loop
    @run_notes_check.before_loop
    @run_send_embeds.before_loop
    @run_web_events_notify.before_loop
    @send_codes_to_channels.before_loop
    @update_supporter_ids.before_loop
    async def before_loops(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Schedule(bot))
