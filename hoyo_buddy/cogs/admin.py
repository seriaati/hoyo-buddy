from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import genshin  # noqa: TC002
from discord.ext import commands
from loguru import logger
from seria.utils import write_json

from hoyo_buddy.commands.leaderboard import LeaderboardCommand
from hoyo_buddy.db import CardSettings, HoyoAccount, Settings, User
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.enums import Game, LeaderboardType
from hoyo_buddy.l10n import translator
from hoyo_buddy.utils import add_to_hoyo_codes

from .search import Search

if TYPE_CHECKING:
    from discord.ext.commands.context import Context

    from ..bot import HoyoBuddy


class Admin(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self._tasks: set[asyncio.Task] = set()

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="sync")
    async def sync_command(self, ctx: commands.Context) -> Any:
        message = await ctx.send("Syncing commands...")
        try:
            synced_commands = await self.bot.tree.sync()
        except Exception:
            await message.edit(content="An error occurred while syncing commands.")
            raise

        await write_json(
            "hoyo_buddy/bot/data/synced_commands.json", {c.name: c.id for c in synced_commands}
        )
        await translator.load_synced_commands_json()
        await message.edit(content=f"Synced {len(synced_commands)} commands.")

    @commands.command(name="reload-translator", aliases=["rtrans"])
    async def fetch_source_strings_command(self, ctx: commands.Context) -> Any:
        await translator.load()
        await ctx.send(content="Reloaded translator.")

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
            asyncio.create_task(search_cog._setup_search_autofill())
        await message.edit(content="Search autocomplete update task started.")

    @commands.command(name="add-codes", aliases=["ac"])
    async def add_codes_command(self, ctx: commands.Context, game: genshin.Game, codes: str) -> Any:
        message = await ctx.send("Adding codes...")
        async with asyncio.TaskGroup() as tg:
            for code in codes.split(","):
                tg.create_task(add_to_hoyo_codes(self.bot.session, code=code, game=game))
        await message.edit(content="Added codes.")

    @commands.command(name="get-accounts", aliases=["ga"])
    async def get_accounts_command(self, ctx: commands.Context, user_id: int | None = None) -> Any:
        user_id = user_id or ctx.author.id
        accounts = await HoyoAccount.filter(user_id=user_id).all()
        if not accounts:
            await ctx.send("No accounts found for this user.")
            return

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

    @commands.command(name="stats")
    async def stats_command(self, ctx: commands.Context) -> Any:
        # Account metrics
        accs = await HoyoAccount.all()
        acc_region_count: defaultdict[genshin.Region, int] = defaultdict(int)
        acc_game_count: defaultdict[Game, int] = defaultdict(int)

        for acc in accs:
            acc_region_count[acc.client.region] += 1
            acc_game_count[acc.game] += 1

        acc_region_msg = "\n".join(
            [f"{region.name}: {count}" for region, count in acc_region_count.items()]
        )
        acc_game_msg = "\n".join(
            [f"{game.name}: {count}" for game, count in acc_game_count.items()]
        )

        guild_count = len(self.bot.guilds)
        await ctx.send(
            f"Guilds: {guild_count}\nAccounts by region:\n```{acc_region_msg}```\nAccounts by game:\n```{acc_game_msg}```\nTotal accounts: {len(accs)}"
        )

        # User metrics
        users = await User.all()
        settings = await Settings.all()
        locale_count: defaultdict[str, int] = defaultdict(int)
        for setting in settings:
            if setting.locale is None:
                continue
            locale_count[setting.locale.value] += 1

        user_count = len(users)
        locale_msg = "\n".join([f"{locale}: {count}" for locale, count in locale_count.items()])
        await ctx.send(f"Users: {user_count}\nLocales:\n```{locale_msg}```")

    @commands.command(name="set-card-settings-game")
    async def set_card_settings_game(self, ctx: commands.Context) -> Any:
        await ctx.send("Starting...")

        settings = await CardSettings.all()
        logger.info(f"Checking {len(settings)} settings...")

        for setting in settings:
            if setting.game is None and len(setting.character_id) == len("10000050"):
                setting.game = Game.GENSHIN
                await setting.save(update_fields=("game",))

        await ctx.send("Done.")

    @commands.command(name="fill-lb")
    async def fill_lb_command(self, ctx: commands.Context) -> Any:
        await ctx.send("Filling leaderboard...")

        cmd = LeaderboardCommand()
        accounts = await HoyoAccount.all()

        game_lb_types = {
            Game.GENSHIN: (
                LeaderboardType.ABYSS_DMG,
                LeaderboardType.THEATER_DMG,
                LeaderboardType.MAX_FRIENDSHIP,
                LeaderboardType.CHEST,
                LeaderboardType.ACHIEVEMENT,
            ),
            Game.STARRAIL: (LeaderboardType.CHEST, LeaderboardType.ACHIEVEMENT),
            Game.ZZZ: (LeaderboardType.ACHIEVEMENT,),
            Game.HONKAI: (LeaderboardType.ACHIEVEMENT,),
        }

        for account in accounts:
            logger.info(f"Updating leaderboard data for {account}")
            for lb_type in game_lb_types.get(account.game, ()):
                try:
                    await cmd.update_lb_data(pool=self.bot.pool, lb_type=lb_type, account=account)
                except Exception as e:
                    self.bot.capture_exception(e)

                await asyncio.sleep(0.5)

        await ctx.send("Done.")

    @commands.command(name="reset-dismissible", aliases=["rd"])
    async def reset_dismissible_command(
        self, ctx: commands.Context, user_id: int | None = None
    ) -> Any:
        await User.filter(id=user_id or ctx.author.id).update(dismissibles=[])
        await ctx.send("Done.")

    @commands.command(name="dismissible-progress", aliases=["dp"])
    async def dismissible_progress_command(self, ctx: commands.Context) -> Any:
        users = await User.all()
        dismissibles: defaultdict[str, int] = defaultdict(int)
        for user in users:
            for dismissible in user.dismissibles:
                dismissibles[dismissible] += 1

        msg = "\n".join([f"{dismissible}: {count}" for dismissible, count in dismissibles.items()])
        await ctx.send(f"Dismissibles:\n```{msg}```")

    @commands.command(name="update-version", aliases=["uv"])
    async def update_version_command(self, ctx: commands.Context) -> Any:
        await self.bot.update_version_activity()
        await ctx.send("Done.")

    @commands.command(name="rcard")
    async def reload_card_data_command(self, ctx: commands.Context) -> Any:
        await CARD_DATA.load()
        await ctx.send("Card data reloaded.")

    @commands.command(name="get-settings", aliases=["gs"])
    async def get_settings_command(self, ctx: commands.Context, user_id: int | None = None) -> Any:
        user_id = user_id or ctx.author.id
        settings = await Settings.get_or_none(user_id=user_id)
        if settings is None:
            return await ctx.send("Settings not found.")

        msg = f"Settings for {user_id}:\n```{settings}```"
        await ctx.send(msg)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Admin(bot))
