from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

import genshin
from discord.ext import commands
from seria.utils import write_json
from tortoise import Tortoise
from tortoise.functions import Count

from hoyo_buddy.config import Deployment
from hoyo_buddy.db import HoyoAccount, Settings, User
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.emojis import get_game_emoji
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
        if self.bot.deployment != "main":
            return

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
    async def fetch_source_strings_command(
        self, ctx: commands.Context, deployment: Deployment
    ) -> Any:
        if deployment != self.bot.deployment:
            return

        await translator.load(force=True)
        await self.bot.start_process_pool()
        await ctx.send(content="Reloaded translator.")

    @commands.command(name="update-assets", aliases=["ua"])
    async def update_assets_command(self, ctx: commands.Context, deployment: Deployment) -> Any:
        if deployment != self.bot.deployment:
            return

        message = await ctx.send("Updating assets...")
        await self.bot.update_assets()
        await message.edit(content="Updated assets.")

    @commands.command(name="update-search-autocomplete", aliases=["usa"])
    async def update_search_autocomplete_command(
        self, ctx: commands.Context, deployment: Deployment
    ) -> Any:
        if deployment != self.bot.deployment:
            return

        message = await ctx.send("Updating search autocomplete...")
        search_cog = self.bot.get_cog("Search")

        if isinstance(search_cog, Search):
            asyncio.create_task(search_cog._setup_search_autofill())
        await message.edit(content="Search autocomplete update task started.")

    @commands.command(name="add-codes", aliases=["ac"])
    async def add_codes_command(self, ctx: commands.Context, game: genshin.Game, codes: str) -> Any:
        if self.bot.deployment != "main":
            return

        message = await ctx.send("Adding codes...")
        for code in codes.split(","):
            try:
                await add_to_hoyo_codes(self.bot.session, code=code, game=game)
            except Exception as e:
                await ctx.send(f"Error adding code {code}: {e}")
                return
            await asyncio.sleep(0.1)
        await message.edit(content="Added codes.")

    @commands.command(name="get-accounts", aliases=["ga"])
    async def get_accounts_command(
        self, ctx: commands.Context, user_id: int | Literal["syrex", "chara"] | None = None
    ) -> Any:
        if self.bot.deployment != "main":
            return

        user_id = user_id or ctx.author.id
        if user_id == "syrex":
            user_id = 781848166458851328
        elif user_id == "chara":
            user_id = 674463869816799243

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
        if self.bot.deployment != "main":
            return None

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
        if self.bot.deployment != "main":
            return

        # Account metrics
        acc_game_counts_list = (
            await HoyoAccount.all()
            .group_by("game")
            .annotate(count=Count("id"))
            .values("game", "count")
        )
        acc_game_count = {item["game"]: item["count"] for item in acc_game_counts_list}
        acc_game_msg = "\n".join(
            [f"{game.name}: {count}" for game, count in acc_game_count.items()]
        )

        acc_region_counts_list = (
            await HoyoAccount.all()
            .group_by("region")
            .annotate(count=Count("id"))
            .values("region", "count")
        )
        acc_region_count = {item["region"]: item["count"] for item in acc_region_counts_list}
        acc_region_msg = "\n".join(
            [f"{region.name}: {count}" for region, count in acc_region_count.items()]
        )

        guild_count = len(self.bot.guilds)
        account_count = await HoyoAccount.all().count()

        await ctx.send(
            f"Guilds: {guild_count}\n"
            "Accounts by region:\n"
            f"```{acc_region_msg}```\n"
            "Accounts by game:\n"
            f"```{acc_game_msg}```\n"
            f"Total accounts: {account_count}"
        )

        # User metrics
        locale_count_list = (
            await Settings.all()
            .group_by("lang")
            .annotate(count=Count("id"))
            .values("lang", "count")
        )
        locale_count = {item["lang"]: item["count"] for item in locale_count_list}
        locale_msg = "\n".join([f"{locale}: {count}" for locale, count in locale_count.items()])

        user_count = await User.all().count()

        await ctx.send(f"Users: {user_count}\nLocales:\n```{locale_msg}```")

    @commands.command(name="reset-dismissible", aliases=["rd"])
    async def reset_dismissible_command(
        self, ctx: commands.Context, user_id: int | None = None
    ) -> Any:
        if self.bot.deployment != "main":
            return

        await User.filter(id=user_id or ctx.author.id).update(dismissibles=[])
        await ctx.send("Done.")

    @commands.command(name="dismissible-progress", aliases=["dp"])
    async def dismissible_progress_command(self, ctx: commands.Context) -> Any:
        if self.bot.deployment != "main":
            return

        raw_sql = """
            SELECT
                element,
                COUNT(*) AS count
            FROM
                "user", -- Note: table name is usually singular
                jsonb_array_elements_text(dismissibles) AS T(element)
            GROUP BY
                element;
        """
        conn = Tortoise.get_connection("default")
        results = await conn.execute_query_dict(raw_sql)
        dismissible_count = {item["element"]: item["count"] for item in results}

        msg = "\n".join(
            [f"{dismissible}: {count}" for dismissible, count in dismissible_count.items()]
        )
        await ctx.send(f"Dismissibles:\n```{msg}```")

    @commands.command(name="update-version", aliases=["uv"])
    async def update_version_command(self, ctx: commands.Context) -> Any:
        if self.bot.deployment != "main":
            return

        await self.bot.update_version_activity()
        await ctx.send("Done.")

    @commands.command(name="rcard")
    async def reload_card_data_command(self, ctx: commands.Context, deployment: Deployment) -> Any:
        if deployment != self.bot.deployment:
            return

        await CARD_DATA.load()
        await ctx.send("Card data reloaded.")

    @commands.command(name="get-settings", aliases=["gs"])
    async def get_settings_command(self, ctx: commands.Context, user_id: int | None = None) -> Any:
        if self.bot.deployment != "main":
            return None

        user_id = user_id or ctx.author.id
        settings = await Settings.get_or_none(user_id=user_id)
        if settings is None:
            return await ctx.send("Settings not found.")

        msg = f"Settings for {user_id}:\n```{settings}```"
        await ctx.send(msg)

    @commands.command(name="enka-hsr-down", aliases=["ehd"])
    async def enka_hsr_down_command(self, ctx: commands.Context, deployment: Deployment) -> Any:
        if deployment != self.bot.deployment:
            return

        self.bot.enka_hsr_down = not self.bot.enka_hsr_down
        status = "down" if self.bot.enka_hsr_down else "up"
        await ctx.send(f"Enka HSR is now marked as {status}.")


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Admin(bot))
