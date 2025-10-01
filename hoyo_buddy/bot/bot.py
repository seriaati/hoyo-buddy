from __future__ import annotations

import asyncio
import atexit
import contextlib
import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import aiocache
import aiosqlite
import anyio
import asyncpg_listen
import discord
import enka
import genshin
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
    HSR_AVATAR_CONFIG_LD_URL,
    HSR_AVATAR_CONFIG_URL,
    HSR_EQUIPMENT_CONFIG_URL,
    HSR_TEXT_MAP_URL,
    POOL_MAX_WORKERS,
    STARRAIL_DATA_LANGS,
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
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, GeetestType, LeaderboardType, Locale, Platform
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

from .command_tree import CommandTree

if TYPE_CHECKING:
    import concurrent.futures
    from collections.abc import Sequence
    from enum import StrEnum

    import asyncpg
    from aiohttp import ClientSession

    from hoyo_buddy.config import Config
    from hoyo_buddy.types import AutocompleteChoices, BetaAutocompleteChoices, Interaction, User

__all__ = ("HoyoBuddy",)


def init_worker() -> None:
    """Initializes the translator in a new process."""
    logger.info(f"Initializing worker process {os.getpid()}...")
    translator.load_sync()

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
            max_messages=None,  # pyright: ignore[reportArgumentType]
            tree_cls=CommandTree,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
            activity=discord.CustomActivity(f"{self.version} | hb.seria.moe"),
        )

        self.session = session
        self.uptime = get_now()
        self.env = config.env
        self.deployment = config.deployment
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

    async def setup_hook(self) -> None:
        await self.start_process_pool()

        # Initialize genshin.py sqlite cache
        async with aiosqlite.connect("genshin_py.db") as conn:
            cache = genshin.SQLiteCache(conn)
            await cache.initialize()

        await self.tree.set_translator(AppCommandTranslator())

        # Preload translators
        await translator.load()

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

        listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(self.config.db_url)
        )
        self.geetest_command_task = asyncio.create_task(
            listener.run({"geetest_command": self.handle_geetest_notify}, notification_timeout=2)
        )

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
        ):
            await asyncio.gather(
                # Update enka.py assets
                enka_gi.update_assets(),
                enka_hsr.update_assets(),
                enka_zzz.update_assets(),
                # Update genshin.py assets
                genshin.utility.update_characters_ambr(),
                # Update item ID -> name mappings and some other stuff
                self.update_zzz_assets(),
                self.update_hsr_assets(),
                # Fetch mi18n files
                translator.fetch_mi18n_files(),
            )

    async def update_zzz_assets(self) -> None:
        result: dict[str, dict[str, str]] = {}

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

        # Item ID -> name mappings
        # Save text maps
        for lang, text_map in text_maps.items():
            await write_json(f"{BOT_DATA_PATH}/zzz_text_map_{lang}.json", text_map)

        item_id_mapping: dict[int, str] = {}  # item ID -> text map key

        first_key = next(iter(item_template.keys()), None)
        if first_key is None:
            logger.error("Cannot find first key in ZZZ item template")
            return

        # Find item keys
        id_key = next((k for k, v in avatar_template[first_key][0].items() if v == 1011), None)
        prop_key = next((k for k, v in avatar_battle_temp[first_key][0].items() if v == [4]), None)
        name_key = next(
            (k for k, v in item_template[first_key][0].items() if v == "Item_Coin"), None
        )

        if not all((id_key, prop_key, name_key)):
            logger.error(
                f"Cannot find required keys in ZZZ game data. {id_key=}, {prop_key=}, {name_key=}"
            )
            return

        for item in item_template[first_key]:
            if any(keyword in item[name_key] for keyword in ("Bangboo_Name", "Item_Weapon")):
                item_id_mapping[item[id_key]] = item[name_key]

        for avatar in avatar_template[first_key]:
            item_id_mapping[avatar[id_key]] = avatar[name_key]

        for lang, text_map in text_maps.items():
            result[lang] = {
                str(item_id): text_map.get(text_map_key, "")
                for item_id, text_map_key in item_id_mapping.items()
            }

        for lang, text_map in result.items():
            await models.JSONFile.write(f"zzz_item_names_{lang}.json", text_map)

        # Agent specialized prop mapping
        prop_mapping: dict[str, list[int]] = {}  # avatar ID -> prop IDs
        for avatar in avatar_battle_temp[first_key]:
            prop_mapping[str(avatar[id_key])] = avatar[prop_key]

        await models.JSONFile.write(ZZZ_AVATAR_BATTLE_TEMP_JSON, prop_mapping)

    async def update_hsr_assets(self) -> None:
        result: dict[str, dict[str, str]] = {}

        async with asyncio.TaskGroup() as tg:
            avatar_config_task = tg.create_task(fetch_json(self.session, HSR_AVATAR_CONFIG_URL))
            avatar_config_ld_task = tg.create_task(
                fetch_json(self.session, HSR_AVATAR_CONFIG_LD_URL)
            )
            equipment_config_task = tg.create_task(
                fetch_json(self.session, HSR_EQUIPMENT_CONFIG_URL)
            )
            text_map_tasks = {
                lang: tg.create_task(fetch_json(self.session, HSR_TEXT_MAP_URL.format(lang=lang)))
                for lang in STARRAIL_DATA_LANGS
            }

        avatar_config = avatar_config_task.result()
        avatar_config_ld = avatar_config_ld_task.result()
        equipment_config = equipment_config_task.result()
        text_maps = {lang: task.result() for lang, task in text_map_tasks.items()}

        item_id_mapping: dict[int, int] = {}  # item ID -> text map key

        for avatar in avatar_config:
            item_id_mapping[avatar["AvatarID"]] = avatar["AvatarName"]["Hash"]

        for avatar in avatar_config_ld:
            item_id_mapping[avatar["AvatarID"]] = avatar["AvatarName"]["Hash"]

        for equipment in equipment_config:
            item_id_mapping[equipment["EquipmentID"]] = equipment["EquipmentName"]["Hash"]

        for lang, text_map in text_maps.items():
            result[lang] = {
                str(item_id): text_map.get(str(text_map_key), "")
                for item_id, text_map_key in item_id_mapping.items()
            }

        for lang, text_map in result.items():
            await models.JSONFile.write(f"hsr_item_names_{lang}.json", text_map)

    async def on_command_error(self, context: commands.Context, e: commands.CommandError) -> None:
        if should_ignore_error(e):
            return

        await context.send(f"An error occurred: {e}")
        self.capture_exception(e)

    async def handle_geetest_notify(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout) or notif.payload is None:
            return

        user_id, message_id, gt_type, account_id, locale, channel_id = notif.payload.split(";")
        gt_type = GeetestType(gt_type)
        locale = Locale(locale)

        message = self.get_partial_messageable(int(channel_id)).get_partial_message(int(message_id))

        user = await models.User.get(id=user_id)
        account = await models.HoyoAccount.get(id=account_id)
        client = account.client

        try:
            if gt_type is GeetestType.DAILY_CHECKIN:
                reward = await client.claim_daily_reward(
                    challenge={
                        "challenge": user.temp_data["geetest_challenge"],
                        "seccode": user.temp_data["geetest_seccode"],
                        "validate": user.temp_data["geetest_validate"],
                    }
                )
                embed = client.get_daily_reward_embed(reward, locale, blur=True)
            else:
                await client.verify_mmt(genshin.models.MMTResult(**user.temp_data))
                embed = DefaultEmbed(locale, title=LocaleStr(key="geeetest_verification_complete"))

            await message.edit(embed=embed, view=None)
        except Exception as e:
            if isinstance(e, discord.HTTPException):
                return

            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                self.capture_exception(e)

            with contextlib.suppress(discord.HTTPException):
                await message.edit(embed=embed, view=None)

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
    def ram_usage(self) -> int:
        """The bot's current RAM usage in MB"""
        return self.process.memory_info().rss / 1024**2

    async def is_owner(
        self, user: discord.User | discord.Member, *, original: bool = False
    ) -> bool:
        if not original and self.deployment != "main":
            return False
        return await super().is_owner(user)
