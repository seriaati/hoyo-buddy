from __future__ import annotations

import asyncio
import atexit
import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import aiocache
import aiosqlite
import anyio
import discord
import enka
import genshin
import hb_data
import psutil
from discord import app_commands
from discord.ext import commands
from loguru import logger
from seria.utils import write_json

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.cache import OrjsonSerializer, image_cache
from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.commands.leaderboard import LeaderboardCommand
from hoyo_buddy.constants import (
    GUILD_ID,
    POOL_MAX_WORKERS,
    ZENLESS_DATA_LANGS,
    ZZZ_AVATAR_BATTLE_TEMP_JSON,
    ZZZ_AVATAR_BATTLE_TEMP_URL,
    ZZZ_AVATAR_TEMPLATE_URL,
    ZZZ_ITEM_TEMPLATE_URL,
    ZZZ_TEXT_MAP_URL,
)
from hoyo_buddy.db import get_locale, models
from hoyo_buddy.db.models import CardSettings, Settings
from hoyo_buddy.db.utils import build_account_query
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.enums import Game, LeaderboardType
from hoyo_buddy.exceptions import NoAccountFoundError
from hoyo_buddy.hoyo.clients.novel_ai import NAIClient
from hoyo_buddy.l10n import BOT_DATA_PATH, AppCommandTranslator, EnumStr, LocaleStr, translator
from hoyo_buddy.utils import (
    capture_exception,
    fetch_json,
    get_now,
    get_project_version,
    should_ignore_error,
)
from hoyo_buddy.utils.gacha_data import update_gacha_data

from .command_tree import CommandTree

if TYPE_CHECKING:
    import concurrent.futures
    from collections.abc import Sequence
    from enum import StrEnum

    import asyncpg
    from aiohttp import ClientSession
    from aiohttp_client_cache.session import CachedSession

    from hoyo_buddy.config import Config
    from hoyo_buddy.enums import Locale, Platform
    from hoyo_buddy.types import AutocompleteChoices, BetaAutocompleteChoices, Interaction, User

__all__ = ("HoyoBuddy",)


def init_worker() -> None:
    """Initializes the translator in a new process."""
    logger.info(f"Initializing worker process {os.getpid()}...")
    translator.load_sync()
    if image_cache is not None:
        image_cache.connect()

    atexit.register(cleanup_worker)


def cleanup_worker() -> None:
    logger.info(f"Cleaning up worker process {os.getpid()}...")
    if image_cache is not None:
        image_cache.disconnect()


class HoyoBuddy(commands.AutoShardedBot):
    def __init__(
        self,
        *,
        session: ClientSession,
        cache_session: CachedSession,
        pool: asyncpg.Pool,
        config: Config,
        executor: concurrent.futures.Executor,
    ) -> None:
        self.version = get_project_version()

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=discord.Intents(guilds=True, members=True, emojis=True, messages=True),
            case_insensitive=True,
            allowed_mentions=discord.AllowedMentions(
                users=True, everyone=False, roles=False, replied_user=False
            ),
            help_command=None,
            chunk_guilds_at_startup=False,
            max_messages=None,
            tree_cls=CommandTree,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
            activity=discord.CustomActivity(f"{self.version} | hb.seria.moe"),
        )

        self.session = session
        self.cache_session = cache_session
        self.uptime = get_now()
        self.env = config.env
        self.nai_client: NAIClient | None = None
        self.pool = pool
        self.config = config

        self.cache = (
            aiocache.Cache.from_url(config.redis_url)
            if config.redis_url
            else aiocache.SimpleMemoryCache()
        )
        self.cache.namespace = "hoyo_buddy"
        self.cache.serializer = OrjsonSerializer()

        self.user_ids: set[int] = set()
        self.process = psutil.Process()
        self.enka_hsr_down = False

        self.search_autofill: AutocompleteChoices = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        self.beta_search_autofill: BetaAutocompleteChoices = defaultdict(lambda: defaultdict(list))

        self.geetest_command_task: asyncio.Task | None = None
        self.farm_check_running: bool = False

        self.executor = executor

    @staticmethod
    def get_command_name(command: app_commands.Command) -> str:
        if command.parent is not None:
            if command.parent.parent is not None:
                return f"{command.parent.parent.name} {command.parent.name} {command.name}"
            return f"{command.parent.name} {command.name}"
        return command.name

    @staticmethod
    def get_lb_type_games(i: Interaction) -> Sequence[Game]:
        if i.namespace.leaderboard is None:
            return []

        try:
            lb = LeaderboardType(i.namespace.leaderboard)
        except ValueError:
            return []

        return LeaderboardCommand.get_games_by_lb_type(lb)

    async def update_version_activity(self) -> None:
        self.version = get_project_version()
        self.activity = discord.CustomActivity(f"{self.version} | hb.seria.moe")
        await self.change_presence(activity=self.activity)

    async def start_process_pool(self) -> None:
        """Starts the process pool and initializes the translators."""
        tasks = [
            self.loop.run_in_executor(self.executor, init_worker) for _ in range(POOL_MAX_WORKERS)
        ]
        await asyncio.gather(*tasks)

    async def _load_cogs(self) -> None:
        async for filepath in anyio.Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = anyio.Path(filepath).stem

            if not self.config.schedule and cog_name == "schedule":
                continue

            if not self.config.prometheus and cog_name == "prometheus":
                continue

            if self.config.is_dev and cog_name == "health":
                continue

            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                logger.info(f"Loaded cog {cog_name!r}")
            except Exception:
                logger.exception(f"Failed to load cog {cog_name!r}")

    async def sync_commands(self) -> list[app_commands.AppCommand]:
        synced_commands = await self.tree.sync()

        await write_json(
            "hoyo_buddy/bot/data/synced_commands.json", {c.name: c.id for c in synced_commands}
        )
        await translator.load_synced_commands_json()
        return synced_commands

    async def setup_hook(self) -> None:
        await self.start_process_pool()

        # Initialize genshin.py sqlite cache
        async with aiosqlite.connect("genshin_py.db") as conn:
            cache = genshin.SQLiteCache(conn)
            await cache.initialize()

        await self.tree.set_translator(AppCommandTranslator())

        # Preload translators
        await translator.load()
        if not translator.loaded:
            await self.update_assets()
            await translator.load()
            await self.start_process_pool()

        await self._load_cogs()
        await self.load_extension("jishaku")

        if self.config.novelai:
            if self.config.nai_token is None or self.config.nai_host_url is None:
                logger.warning(
                    "NovelAI token or host URL is not set, skipping NAI client initialization."
                )
            else:
                self.nai_client = NAIClient(
                    token=self.config.nai_token, host_url=self.config.nai_host_url
                )
                await self.nai_client.init(timeout=120)

        users = await models.User.all().only("id")
        for user in users:
            self.user_ids.add(user.id)

        await CARD_DATA.load()
        self.loop.set_exception_handler(self.asyncio_erorr_handler)

        shards, _gateway_url, _session_limit = await self.http.get_bot_gateway()
        logger.info(f"Spawning {shards} shards")

    async def get_or_fetch_guild(self) -> discord.Guild | None:
        guild_id = GUILD_ID
        guild = self.get_guild(guild_id)
        if guild is None:
            try:
                guild = await self.fetch_guild(guild_id)
            except discord.HTTPException:
                logger.error(f"Failed to fetch guild with ID {guild_id}")
                return None
        return guild

    def capture_exception(self, e: Exception) -> None:
        capture_exception(e)

    async def dm_user(
        self, user_id: int, *, content: str | None = None, **kwargs
    ) -> tuple[discord.Message | None, bool]:
        logger.debug(f"DMing user {user_id}")

        try:
            channel = await models.DMChannel.get_or_none(user_id=user_id)
            if channel is None:
                user = self.get_user(user_id) or await self.fetch_user(user_id)
                dm_channel = user.dm_channel or await user.create_dm()
                channel = await models.DMChannel.create(user_id=user_id, id=dm_channel.id)
            message = await self.get_partial_messageable(channel.id).send(content, **kwargs)
        except discord.Forbidden:
            return None, False
        except Exception as e:
            self.capture_exception(e)
            return None, True
        else:
            return message, False

    def get_error_choice(
        self, error_message: LocaleStr | str | Exception, locale: Locale
    ) -> list[app_commands.Choice[str]]:
        if isinstance(error_message, Exception):
            embed, recognized = get_error_embed(error_message, locale)
            if not recognized:
                self.capture_exception(error_message)

            if embed.title is not None:
                err_message = embed.title
                if embed.description is not None:
                    err_message += f": {embed.description}"
                    if len(err_message) > 100:
                        err_message = embed.title

                return self.get_error_choice(err_message, locale)

            return self.get_error_choice(str(error_message), locale)

        return [app_commands.Choice(name=translator.translate(error_message, locale), value="none")]

    def get_enum_choices(
        self, enums: Sequence[StrEnum], locale: Locale, current: str
    ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(name=EnumStr(enum).translate(locale), value=enum.value)
            for enum in enums
            if current.lower() in EnumStr(enum).translate(locale).lower()
        ]

    @staticmethod
    def _get_account_choice_name(
        account: models.HoyoAccount, locale: Locale, *, is_author: bool, show_id: bool
    ) -> str:
        account_id_str = f"[{account.id}] " if show_id else ""
        account_display = account if is_author else account.blurred_display
        game_str = translator.translate(EnumStr(account.game), locale)
        current_str = " (✦)" if account.current else ""
        return f"{account_id_str}{account_display} | {game_str}{current_str}"

    async def get_account_choices(
        self,
        user: User,
        author_id: int,
        current: str,
        locale: Locale,
        *,
        games: Sequence[Game],
        platform: Platform | None = None,
        show_id: bool = False,
    ) -> list[discord.app_commands.Choice[str]]:
        """Get autocomplete choices for a user's accounts.

        Args:
            user: The user object to query the accounts with.
            author_id: The interaction author's ID.
            current: The current input.
            locale: Discord locale.
            games: The games to filter by
            platform: The platform to filter by.
            show_id: Whether to show the account ID.
        """
        is_author = user is None or user.id == author_id

        query = build_account_query(
            games=games, platform=platform, user_id=author_id if user is None else user.id
        )
        accounts = await models.HoyoAccount.filter(query)
        if not is_author:
            accounts = [account for account in accounts if account.public]

        if not accounts:
            if is_author:
                return self.get_error_choice(
                    LocaleStr(key="no_accounts_autocomplete_choice"), locale
                )
            return self.get_error_choice(
                LocaleStr(key="user_no_accounts_autocomplete_choice"), locale
            )

        return [
            discord.app_commands.Choice(
                name=self._get_account_choice_name(
                    account, locale, is_author=is_author, show_id=show_id
                ),
                value=str(account.id),
            )
            for account in accounts
            if current.lower() in str(account).lower()
        ]

    async def get_game_account_choices(
        self, i: Interaction, current: str, *, show_id: bool = False
    ) -> list[app_commands.Choice[str]]:
        if not isinstance(i.command, app_commands.Command):
            logger.error(
                f"Cannot use `get_game_account_choices` on a non-slash command, using: {type(i.command)}"
            )
            return []

        command_name = self.get_command_name(i.command)
        command = COMMANDS.get(command_name)  # pyright: ignore[reportArgumentType]
        if command is None:
            logger.error(f"Failed to get command config with name {command_name!r}")
            return []

        games = command.games or []

        lb_type_games = self.get_lb_type_games(i)
        if lb_type_games:
            games = list(games)
            games.extend(lb_type_games)

        if not games:
            # lb view command may not have games because user selects invalid lb type
            if command_name != "lb view":
                logger.error(
                    f"Cannot use `get_game_account_choices` on commands without games explicitly set, command: {command_name}"
                )
            return []

        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.get_account_choices(
            user,
            i.user.id,
            current,
            locale,
            games=games,
            platform=command.platform,
            show_id=show_id,
        )

    async def get_accounts(
        self, user_id: int, games: Sequence[Game] | None, platform: Platform | None = None
    ) -> list[models.HoyoAccount]:
        """Get accounts by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platform: The platform to filter by.
        """
        if games is None:
            logger.warning("Getting account without specifying games, this is not recommended.")
            games = list(Game)

        query = build_account_query(games=games, platform=platform)
        accounts = await models.HoyoAccount.filter(query, user_id=user_id).all()
        if not accounts:
            raise NoAccountFoundError(games, platform)

        return accounts

    async def get_account(
        self, user_id: int, games: Sequence[Game] | None, platform: Platform | None = None
    ) -> models.HoyoAccount:
        """Get an account by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platform: The platform to filter by.
        """
        accounts = await self.get_accounts(user_id, games, platform)
        current_accounts = [account for account in accounts if account.current]
        await self.sanitize_accounts(user_id)
        return current_accounts[0] if current_accounts else accounts[0]

    @staticmethod
    async def sanitize_accounts(user_id: int) -> None:
        """Sanitize the Hoyo accounts for a given user by ensuring only one account is marked as current.

        This method performs the following actions:
        1. Retrieves all Hoyo accounts associated with the given user ID.
        2. Checks if there are any accounts marked as current.
        3. If no accounts are marked as current and there are accounts available, marks the first account as current.
        4. If more than one account is marked as current, resets all accounts to not current and marks only the first account as current.

        Args:
            user_id: The ID of the user whose accounts need to be sanitized.
        """
        accounts = await models.HoyoAccount.filter(user_id=user_id).all()
        current_accounts = [account for account in accounts if account.current]
        if not current_accounts and accounts:
            await models.HoyoAccount.filter(id=accounts[0].id).update(current=True)
            return

        if len(current_accounts) > 1:
            await models.HoyoAccount.filter(user_id=user_id).update(current=False)
            await models.HoyoAccount.filter(id=current_accounts[0].id).update(current=True)

    async def update_assets(self) -> None:
        # Update enka.py assets
        async with (
            enka.GenshinClient() as enka_gi,
            enka.HSRClient() as enka_hsr,
            enka.ZZZClient() as enka_zzz,
            hb_data.GIClient() as gi_client,
            hb_data.ZZZClient() as zzz_client,
        ):
            await asyncio.gather(
                # Update enka.py assets
                enka_gi.update_assets(),
                enka_hsr.update_assets(),
                enka_zzz.update_assets(),
                # Update genshin.py assets
                genshin.utility.update_characters_ambr(),
                # Update ZZZ agent specialized prop mapping
                self.update_zzz_assets(),
                # Fetch gacha data from official APIs
                update_gacha_data(self.session),
                # Fetch mi18n files
                translator.fetch_mi18n_files(),
                # hb-data
                gi_client.download(force=True),
                zzz_client.download(force=True),
            )

    async def update_zzz_assets(self) -> None:
        async with asyncio.TaskGroup() as tg:
            item_temp_task = tg.create_task(fetch_json(self.session, ZZZ_ITEM_TEMPLATE_URL))
            avatar_temp_task = tg.create_task(fetch_json(self.session, ZZZ_AVATAR_TEMPLATE_URL))
            text_map_tasks = {
                lang: tg.create_task(fetch_json(self.session, ZZZ_TEXT_MAP_URL.format(lang=lang)))
                for lang in ZENLESS_DATA_LANGS
            }
            avatar_battle_temp_task = tg.create_task(
                fetch_json(self.session, ZZZ_AVATAR_BATTLE_TEMP_URL)
            )

        item_template = item_temp_task.result()
        avatar_template = avatar_temp_task.result()
        avatar_battle_temp = avatar_battle_temp_task.result()
        text_maps = {lang: task.result() for lang, task in text_map_tasks.items()}

        for lang, text_map in text_maps.items():
            await write_json(f"{BOT_DATA_PATH}/zzz_text_map_{lang}.json", text_map)

        first_key = next(iter(item_template.keys()), None)
        if first_key is None:
            logger.error("Cannot find first key in ZZZ item template")
            return

        id_key = next((k for k, v in avatar_template[first_key][0].items() if v == 1011), None)
        prop_key = next((k for k, v in avatar_battle_temp[first_key][0].items() if v == [4]), None)

        if not all((id_key, prop_key)):
            logger.error(f"Cannot find required keys in ZZZ game data. {id_key=}, {prop_key=}")
            return

        prop_mapping: dict[str, list[int]] = {}
        for avatar in avatar_battle_temp[first_key]:
            prop_mapping[str(avatar[id_key])] = avatar[prop_key]

        await models.JSONFile.write(ZZZ_AVATAR_BATTLE_TEMP_JSON, prop_mapping)

    async def on_command_error(self, context: commands.Context, e: commands.CommandError) -> None:
        if should_ignore_error(e):
            return

        await context.send(f"An error occurred: {e}")
        self.capture_exception(e)

    def asyncio_erorr_handler(self, _: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
        exception = context.get("exception")
        message = context.get("message")
        task = context.get("task")

        if exception is not None:
            self.capture_exception(exception)
        else:
            logger.error(f"Unhandled exception in task {task!r} with message {message!r}")

    async def close(self) -> None:
        logger.info("Bot shutting down...")
        if self.geetest_command_task is not None:
            self.geetest_command_task.cancel()

        await Settings.close_redis_pool()
        await CardSettings.close_redis_pool()

        await super().close()

    @property
    def ram_usage(self) -> float:
        """The bot's current RAM usage in MB"""
        return self.process.memory_info().rss / 1024**2
