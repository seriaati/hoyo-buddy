from __future__ import annotations

import concurrent.futures
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import discord
import enka
import genshin
import sentry_sdk
from asyncache import cached
from cachetools import TTLCache
from discord import app_commands
from discord.ext import commands
from tortoise.expressions import Q

from ..db.models import HoyoAccount
from ..enums import Platform
from ..exceptions import NoAccountFoundError
from ..hoyo.clients.novel_ai import NAIClient
from ..utils import get_now
from .command_tree import CommandTree
from .translator import AppCommandTranslator, LocaleStr, Translator

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Sequence

    import asyncpg
    import git
    from aiohttp import ClientSession

    from ..enums import Game
    from ..hoyo.clients import ambr, yatta


__all__ = ("INTERACTION", "HoyoBuddy")

LOGGER_ = logging.getLogger(__name__)
INTERACTION: TypeAlias = discord.Interaction["HoyoBuddy"]
USER: TypeAlias = discord.User | discord.Member | None
STATUS_CHANNEL_ID = 1220175609347444776

intents = discord.Intents(
    guilds=True,
    members=True,
    emojis=True,
    messages=True,
)
allowed_mentions = discord.AllowedMentions(
    users=True,
    everyone=False,
    roles=False,
    replied_user=False,
)


class HoyoBuddy(commands.AutoShardedBot):
    owner_id: int

    def __init__(
        self,
        *,
        session: ClientSession,
        env: str,
        translator: Translator,
        repo: git.Repo,
        version: str,
        pool: asyncpg.Pool,
    ) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            help_command=None,
            chunk_guilds_at_startup=False,
            max_messages=None,
            member_cache_flags=discord.MemberCacheFlags.none(),
            tree_cls=CommandTree,
            activity=discord.CustomActivity(f"{version} | hb.bot.nu"),
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
        )
        self.session = session
        self.uptime = get_now()
        self.translator = translator
        self.env = env
        self.nai_client = NAIClient(
            token=os.environ["NAI_TOKEN"], host_url=os.environ["NAI_HOST_URL"]
        )
        self.owner_id = 410036441129943050
        self.repo = repo
        self.version = version
        self.pool = pool
        self.executor = concurrent.futures.ProcessPoolExecutor()

        self.search_autocomplete_choices: dict[
            Game,
            dict[
                ambr.ItemCategory | yatta.ItemCategory,
                dict[str, dict[str, str]],
            ],
        ] = {}
        """[game][category][locale][item_name] -> item_id"""

        self.login_notif_tasks: dict[int, asyncio.Task] = {}
        """user_id -> task"""

    async def setup_hook(self) -> None:
        await self.tree.set_translator(AppCommandTranslator(self.translator))

        for filepath in Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                LOGGER_.info("Loaded cog %r", cog_name)
            except Exception:
                LOGGER_.exception("Failed to load cog %r", cog_name)

        await self.load_extension("jishaku")

        await self.nai_client.init(timeout=120)

        if self.env != "dev":
            await self._send_status_embed("start")

    async def _send_status_embed(self, status: Literal["start", "stop"]) -> None:
        """Send a status embed to the status channel.

        Args:
            status: The status of the bot.
        """
        status_channel = await self.fetch_channel(STATUS_CHANNEL_ID)
        assert isinstance(status_channel, discord.TextChannel)

        embed = discord.Embed(
            title=f"Bot {'Started 🚀' if status == 'start' else 'Shutting Down for Code Update 🛠️'}",
            description=f"Current time: {discord.utils.format_dt(get_now(), 'T')}",
            color=discord.Color.green() if status == "start" else discord.Color.red(),
        )
        await status_channel.send(embed=embed)

    def capture_exception(self, e: Exception) -> None:
        if self.env == "dev":
            LOGGER_.exception(e)
        else:
            sentry_sdk.capture_exception(e)

    @cached(cache=TTLCache(maxsize=1024, ttl=360))
    async def fetch_user(self, user_id: int) -> discord.User | None:
        try:
            user = await super().fetch_user(user_id)
        except (discord.NotFound, discord.HTTPException):
            return None
        else:
            return user

    async def dm_user(self, user_id: int, **kwargs: Any) -> discord.Message | None:
        user = await self.fetch_user(user_id)
        if user is None:
            return None

        try:
            message = await user.send(**kwargs)
        except Exception:
            return None

        return message

    @staticmethod
    def get_error_app_command_choice(error_message: LocaleStr) -> app_commands.Choice[str]:
        return app_commands.Choice(
            name=error_message.to_app_command_locale_str(),
            value="none",
        )

    async def get_account_autocomplete(
        self,
        user: USER,
        author_id: int,
        current: str,
        locale: discord.Locale,
        translator: Translator,
        games: Sequence[Game],
        platforms: Sequence[Platform] | None = None,
    ) -> list[discord.app_commands.Choice[str]]:
        """Get autocomplete choices for a user's accounts.

        Args:
            user: The user object to query the accounts with.
            author_id: The interaction author's ID.
            current: The current input.
            locale: Discord locale.
            translator: Bot's translator.
            games: The games to filter by
            platforms: The platforms to filter by.
        """
        is_author = user is None or user.id == author_id
        game_query = Q(*[Q(game=game) for game in games], join_type="OR")
        accounts = await HoyoAccount.filter(
            game_query, user_id=author_id if user is None else user.id
        ).all()
        if not is_author:
            accounts = [account for account in accounts if account.public]

        platforms = platforms or list(Platform)
        accounts = [account for account in accounts if account.platform in platforms]

        if not accounts:
            if is_author:
                return [
                    self.get_error_app_command_choice(
                        LocaleStr(
                            "You don't have any accounts yet. Add one with /accounts",
                            key="no_accounts_autocomplete_choice",
                        )
                    )
                ]
            return [
                self.get_error_app_command_choice(
                    LocaleStr(
                        "This user doesn't have any accounts yet",
                        key="user_no_accounts_autocomplete_choice",
                    )
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account if is_author else account.blurred_display} | {translator.translate(LocaleStr(account.game, warn_no_key=False), locale)}{' (✦)' if account.current else ''}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current.lower() in str(account).lower()
        ]

    @staticmethod
    async def get_account(
        user_id: int, games: Sequence[Game], platforms: Sequence[Platform] | None = None
    ) -> HoyoAccount:
        """Get an account by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platforms: The platforms to filter by.
        """
        platforms = platforms or list(Platform)

        game_query = Q(*[Q(game=game) for game in games], join_type="OR")
        accounts = await HoyoAccount.filter(game_query, user_id=user_id).all()
        accounts = [account for account in accounts if account.platform in platforms]
        if not accounts:
            raise NoAccountFoundError(games, platforms)

        current_accounts = [account for account in accounts if account.current]
        if current_accounts:
            return current_accounts[0]
        else:
            account = accounts[0]
            account.current = True
            await account.save(update_fields=("current",))
            return account

    async def update_assets(self) -> None:
        # Update EnkaAPI assets
        async with enka.GenshinClient() as api:
            await api.update_assets()

        async with enka.HSRClient() as api:
            await api.update_assets()

        # Update genshin.py assets
        await genshin.utility.update_characters_any()

    async def on_command_error(
        self, context: commands.Context, exception: commands.CommandError
    ) -> None:
        if isinstance(exception, commands.CommandNotFound):
            return
        return await super().on_command_error(context, exception)

    async def close(self) -> None:
        LOGGER_.info("Bot shutting down...")
        if self.env != "dev":
            await self._send_status_embed("stop")

        for task in self.login_notif_tasks.values():
            task.cancel()

        await super().close()
