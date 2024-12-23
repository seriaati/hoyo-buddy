from __future__ import annotations

import asyncio
import concurrent.futures
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aioconsole
import aiohttp
import aiosqlite
import asyncpg_listen
import discord
import enka
import genshin
import git
import sentry_sdk
from asyncache import cached
from cachetools import TTLCache
from discord import app_commands
from discord.ext import commands
from loguru import logger
from seria.utils import write_json
from tortoise.expressions import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import (
    HSR_AVATAR_CONFIG_URL,
    HSR_EQUIPMENT_CONFIG_URL,
    HSR_TEXT_MAP_URL,
    STARRAIL_DATA_LANGS,
    ZENLESS_DATA_LANGS,
    ZZZ_AVATAR_BATTLE_TEMP_JSON,
    ZZZ_AVATAR_BATTLE_TEMP_URL,
    ZZZ_AVATAR_TEMPLATE_URL,
    ZZZ_ITEM_TEMPLATE_URL,
    ZZZ_TEXT_MAP_URL,
)
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimo
from hoyo_buddy.hoyo.auto_tasks.auto_redeem import AutoRedeem
from hoyo_buddy.hoyo.auto_tasks.daily_checkin import DailyCheckin

from ..db import get_locale, models
from ..enums import Game, GeetestType, Platform
from ..exceptions import NoAccountFoundError
from ..hoyo.clients.novel_ai import NAIClient
from ..l10n import BOT_DATA_PATH, AppCommandTranslator, EnumStr, LocaleStr, translator
from ..utils import fetch_json, get_now, get_repo_version
from .cache import LFUCache
from .command_tree import CommandTree

if TYPE_CHECKING:
    from collections.abc import Sequence
    from enum import StrEnum

    import asyncpg
    from aiohttp import ClientSession

    from ..models import Config
    from ..types import AutocompleteChoices, BetaAutocompleteChoices, Interaction, User

__all__ = ("HoyoBuddy",)


class HoyoBuddy(commands.AutoShardedBot):
    owner_id: int

    def __init__(
        self, *, session: ClientSession, env: str, pool: asyncpg.Pool, config: Config
    ) -> None:
        self.repo = git.Repo()
        self.version = get_repo_version()

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
            member_cache_flags=discord.MemberCacheFlags.none(),
            tree_cls=CommandTree,
            allowed_contexts=discord.app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True),
            activity=discord.CustomActivity(f"{self.version} | hb.seria.moe"),
        )

        self.session = session
        self.uptime = get_now()
        self.env = env
        self.nai_client = NAIClient(
            token=os.environ["NAI_TOKEN"], host_url=os.environ["NAI_HOST_URL"]
        )
        self.owner_id = 410036441129943050
        self.guild_id = 1000727526194298910
        self.pool = pool
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.config = config
        self.cache = LFUCache()
        self.user_ids: set[int] = set()

        self.autocomplete_choices: AutocompleteChoices = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        """[game][category][locale][item_name] -> item_id"""
        self.beta_autocomplete_choices: BetaAutocompleteChoices = defaultdict(
            lambda: defaultdict(list)
        )
        """[game][locale][item_name] -> item_id"""

        self.geetest_command_task: asyncio.Task | None = None
        self.farm_check_running: bool = False

    async def setup_hook(self) -> None:
        # Initialize genshin.py sqlite cache
        async with aiosqlite.connect("genshin_py.db") as conn:
            cache = genshin.SQLiteCache(conn)
            await cache.initialize()

        await self.tree.set_translator(AppCommandTranslator())

        for filepath in Path("hoyo_buddy/cogs").glob("**/*.py"):
            cog_name = Path(filepath).stem
            try:
                await self.load_extension(f"hoyo_buddy.cogs.{cog_name}")
                logger.info(f"Loaded cog {cog_name!r}")
            except Exception:
                logger.exception(f"Failed to load cog {cog_name!r}")

        await self.load_extension("jishaku")

        await self.nai_client.init(timeout=120)

        users = await models.User.all().only("id")
        for user in users:
            self.user_ids.add(user.id)

        listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        self.geetest_command_task = asyncio.create_task(
            listener.run({"geetest_command": self.handle_geetest_notify}, notification_timeout=2)
        )

    def capture_exception(self, e: Exception) -> None:
        # Errors to suppress
        if isinstance(e, aiohttp.ClientConnectorError | aiohttp.ServerDisconnectedError):
            return
        if isinstance(e, discord.NotFound) and e.code == 10062:
            # Unknown interaction
            return

        if not self.config.sentry:
            logger.exception(e)
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
        except (discord.Forbidden, discord.HTTPException):
            return None
        except Exception as e:
            self.capture_exception(e)
            return None

        return message

    def get_error_choice(
        self, error_message: LocaleStr | str | Exception, locale: discord.Locale
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
        self, enums: Sequence[StrEnum], locale: discord.Locale, current: str
    ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(name=EnumStr(enum).translate(locale), value=enum.value)
            for enum in enums
            if current.lower() in EnumStr(enum).translate(locale).lower()
        ]

    @staticmethod
    def _get_account_choice_name(
        account: models.HoyoAccount, locale: discord.Locale, *, is_author: bool, show_id: bool
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
        locale: discord.Locale,
        *,
        games: Sequence[Game] | None = None,
        platforms: Sequence[Platform] | None = None,
        show_id: bool = False,
    ) -> list[discord.app_commands.Choice[str]]:
        """Get autocomplete choices for a user's accounts.

        Args:
            user: The user object to query the accounts with.
            author_id: The interaction author's ID.
            current: The current input.
            locale: Discord locale.
            games: The games to filter by
            platforms: The platforms to filter by.
            show_id: Whether to show the account ID.
        """
        games = games or list(Game)
        is_author = user is None or user.id == author_id
        game_query = Q(*[Q(game=game) for game in games], join_type="OR")
        accounts = await models.HoyoAccount.filter(
            game_query, user_id=author_id if user is None else user.id
        ).all()
        if not is_author:
            accounts = [account for account in accounts if account.public]

        platforms = platforms or list(Platform)
        accounts = [account for account in accounts if account.platform in platforms]

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
        self,
        i: Interaction,
        current: str,
        games: Sequence[Game] | None = None,
        platforms: Sequence[Platform] | None = None,
    ) -> list[app_commands.Choice[str]]:
        games = games or list(Game)
        locale = await get_locale(i)
        user: User = i.namespace.user
        return await self.get_account_choices(
            user, i.user.id, current, locale, games=games, platforms=platforms
        )

    async def get_accounts(
        self, user_id: int, games: Sequence[Game] | None = None, platform: Platform | None = None
    ) -> list[models.HoyoAccount]:
        """Get accounts by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platforms: The platforms to filter by.
        """
        games = games or list(Game)
        platforms = [platform] if platform else list(Platform)

        game_query = Q(*[Q(game=game) for game in games], join_type="OR")
        accounts = await models.HoyoAccount.filter(game_query, user_id=user_id).all()
        accounts = [account for account in accounts if account.platform in platforms]
        if not accounts:
            raise NoAccountFoundError(games, platform)

        return accounts

    async def get_account(
        self, user_id: int, games: Sequence[Game] | None = None, platform: Platform | None = None
    ) -> models.HoyoAccount:
        """Get an account by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platforms: The platforms to filter by.
        """
        accounts = await self.get_accounts(user_id, games, platform)
        current_accounts = [account for account in accounts if account.current]
        await self.sanitize_accounts(user_id)
        return current_accounts[0] if current_accounts else accounts[0]

    @staticmethod
    async def sanitize_accounts(user_id: int) -> None:
        """Sanitize accounts for a user.

        Args:
            user_id: The user ID to sanitize the accounts for.
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
        async with (
            enka.GenshinClient() as enka_gi,
            enka.HSRClient() as enka_hsr,
            asyncio.TaskGroup() as tg,
        ):
            # Fetch mi18n files
            tg.create_task(translator.fetch_mi18n_files())

            # Update enka.py assets
            tg.create_task(enka_gi.update_assets())
            tg.create_task(enka_hsr.update_assets())

            # Update genshin.py assets
            tg.create_task(genshin.utility.update_characters_ambr())

            # Update item ID -> name mappings and some other stuff
            tg.create_task(self.update_zzz_assets())
            tg.create_task(self.update_hsr_assets())

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

        # Item ID -> name mappings
        item_template = item_temp_task.result()
        avatar_template = avatar_temp_task.result()
        text_maps = {lang: task.result() for lang, task in text_map_tasks.items()}

        # Save text maps
        for lang, text_map in text_maps.items():
            await write_json(f"{BOT_DATA_PATH}/zzz_text_map_{lang}.json", text_map)

        item_id_mapping: dict[int, str] = {}  # item ID -> text map key

        first_key = next(iter(item_template.keys()), None)
        if first_key is None:
            logger.error("Cannot find first key in ZZZ item template")
            return

        id_key = "FJKECLFEHOA"  # Found in ItemTemplateTb.json
        name_key = "JOMJELIIAGO"  # Found in ItemTemplateTb.json
        prop_key = "OGIDKDJDHCL"  # Found in AvatarBaseTemplateTb.json

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
        avatar_battle_temp = avatar_battle_temp_task.result()

        prop_mapping: dict[str, list[int]] = {}  # avatar ID -> prop IDs
        for avatar in avatar_battle_temp[first_key]:
            prop_mapping[str(avatar[id_key])] = avatar[prop_key]

        await models.JSONFile.write(ZZZ_AVATAR_BATTLE_TEMP_JSON, prop_mapping)

    async def update_hsr_assets(self) -> None:
        result: dict[str, dict[str, str]] = {}

        async with asyncio.TaskGroup() as tg:
            avatar_config_task = tg.create_task(fetch_json(self.session, HSR_AVATAR_CONFIG_URL))
            equipment_config_task = tg.create_task(
                fetch_json(self.session, HSR_EQUIPMENT_CONFIG_URL)
            )
            text_map_tasks = {
                lang: tg.create_task(fetch_json(self.session, HSR_TEXT_MAP_URL.format(lang=lang)))
                for lang in STARRAIL_DATA_LANGS
            }

        avatar_config = avatar_config_task.result()
        equipment_config = equipment_config_task.result()
        text_maps = {lang: task.result() for lang, task in text_map_tasks.items()}

        item_id_mapping: dict[int, int] = {}  # item ID -> text map key

        for avatar in avatar_config:
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

    async def on_command_error(
        self, context: commands.Context, exception: commands.CommandError
    ) -> None:
        if isinstance(exception, commands.CommandNotFound | commands.TooManyArguments):
            return None
        return await super().on_command_error(context, exception)

    async def handle_geetest_notify(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout) or notif.payload is None:
            return

        user_id, message_id, gt_type, account_id, locale, channel_id = notif.payload.split(";")
        gt_type = GeetestType(gt_type)
        locale = discord.Locale(locale)

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
            if isinstance(e, discord.Forbidden):
                return

            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                self.capture_exception(e)
            await message.edit(embed=embed, view=None)

    async def close(self) -> None:
        tasks = (AutoRedeem, AutoMimo, DailyCheckin)
        if any(task._lock.locked() for task in tasks) or self.farm_check_running:
            logger.warning("Task(s) are still running, still close the bot? (y/n)")
            response: str = await aioconsole.ainput()
            if response.lower() != "y":
                return

        logger.info("Bot shutting down...")
        if self.geetest_command_task is not None:
            self.geetest_command_task.cancel()

        self.executor.shutdown()
        await super().close()
