import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

import discord
import diskcache
import sentry_sdk
from asyncache import cached
from cachetools import TTLCache
from discord import app_commands
from discord.ext import commands

from ..db.models import HoyoAccount
from ..hoyo.clients.novelai_client import NAIClient
from ..utils import get_now
from .command_tree import CommandTree
from .translator import AppCommandTranslator, LocaleStr, Translator

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from ..enums import Game
    from ..hoyo.clients import ambr_client, yatta_client

LOGGER_ = logging.getLogger(__name__)

__all__ = ("HoyoBuddy", "INTERACTION")

INTERACTION: TypeAlias = discord.Interaction["HoyoBuddy"]

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
        session: "ClientSession",
        env: str,
        translator: Translator,
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
        )
        self.session = session
        self.uptime = get_now()
        self.translator = translator
        self.env = env
        self.diskcache = diskcache.Cache("./.cache/hoyo_buddy")
        self.nai_client = NAIClient(
            token=os.environ["NAI_TOKEN"], host_url=os.environ["NAI_HOST_URL"]
        )
        self.owner_id = 410036441129943050

        self.search_autocomplete_choices: dict[
            Game,
            dict[
                ambr_client.ItemCategory | yatta_client.ItemCategory,
                dict[str, dict[str, str]],
            ],
        ] = {}
        """[game][category][locale][item_name] -> item_id"""

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

    def capture_exception(self, e: Exception) -> None:
        if self.env == "prod":
            sentry_sdk.capture_exception(e)
        else:
            LOGGER_.exception(e)

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

    @staticmethod
    async def _get_account_autocomplete(
        user_id: int,
        current: str,
        locale: discord.Locale,
        translator: Translator,
        games: set["Game"] | None = None,
    ) -> list[discord.app_commands.Choice[str]]:
        accounts = await HoyoAccount.filter(user_id=user_id).all()
        if not accounts:
            return [
                discord.app_commands.Choice(
                    name=discord.app_commands.locale_str(
                        "You don't have any accounts yet. Add one with /accounts",
                        key="no_accounts_autocomplete_choice",
                    ),
                    value="none",
                )
            ]

        return [
            discord.app_commands.Choice(
                name=f"{account} | {translator.translate(LocaleStr(account.game, warn_no_key=False), locale)}",
                value=f"{account.uid}_{account.game}",
            )
            for account in accounts
            if current.lower() in str(account).lower() and (games is None or account.game in games)
        ]

    async def close(self) -> None:
        LOGGER_.info("Bot shutting down...")
        self.diskcache.close()
        await super().close()
