from __future__ import annotations

import asyncio
import concurrent.futures
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
from tortoise.expressions import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import (
    HSR_AVATAR_CONFIG_URL,
    HSR_EQUIPMENT_CONFIG_URL,
    HSR_TEXT_MAP_URL,
    STARRAIL_DATA_LANGS,
    ZENLESS_DATA_LANGS,
    ZZZ_AVATAR_TEMPLATE_URL,
    ZZZ_ITEM_TEMPLATE_URL,
    ZZZ_TEXT_MAP_URL,
)
from hoyo_buddy.embeds import DefaultEmbed

from ..db import models
from ..enums import Game, GeetestType, Platform
from ..exceptions import NoAccountFoundError
from ..hoyo.clients.novel_ai import NAIClient
from ..l10n import AppCommandTranslator, EnumStr, LocaleStr, Translator
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
        self,
        *,
        session: ClientSession,
        env: str,
        translator: Translator,
        pool: asyncpg.Pool,
        config: Config,
    ) -> None:
        self.repo = git.Repo()
        self.version = get_repo_version(self.repo)

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
            activity=discord.CustomActivity(f"{self.version} | hb.seria.moe"),
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

    async def setup_hook(self) -> None:
        # Initialize genshin.py sqlite cache
        async with aiosqlite.connect("genshin_py.db") as conn:
            cache = genshin.SQLiteCache(conn)
            await cache.initialize()

        await self.tree.set_translator(AppCommandTranslator(self.translator))

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

        return message

    def get_error_choice(
        self, error_message: LocaleStr, locale: discord.Locale
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=error_message.translate(self.translator, locale), value="none")
        ]

    def get_enum_choices(
        self, enums: Sequence[StrEnum], locale: discord.Locale, current: str
    ) -> list[discord.app_commands.Choice[str]]:
        return [
            discord.app_commands.Choice(
                name=EnumStr(enum).translate(self.translator, locale), value=enum.value
            )
            for enum in enums
            if current.lower() in EnumStr(enum).translate(self.translator, locale).lower()
        ]

    @staticmethod
    def _get_account_choice_name(
        account: models.HoyoAccount,
        locale: discord.Locale,
        translator: Translator,
        *,
        is_author: bool,
        show_id: bool,
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
        translator: Translator,
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
            translator: Bot's translator.
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
                    account, locale, translator, is_author=is_author, show_id=show_id
                ),
                value=str(account.id),
            )
            for account in accounts
            if current.lower() in str(account).lower()
        ]

    async def get_game_account_choices(
        self, i: Interaction, current: str, games: Sequence[Game] | None = None
    ) -> list[app_commands.Choice[str]]:
        games = games or list(Game)
        locale = await models.get_locale(i)
        user: User = i.namespace.user
        return await self.get_account_choices(
            user, i.user.id, current, locale, self.translator, games=games
        )

    async def get_account(
        self,
        user_id: int,
        games: Sequence[Game] | None = None,
        platforms: Sequence[Platform] | None = None,
    ) -> models.HoyoAccount:
        """Get an account by user ID and games.

        Args:
            user_id: The Discord user ID.
            games: The games to filter by.
            platforms: The platforms to filter by.
        """
        games = games or list(Game)
        platforms = platforms or list(Platform)

        game_query = Q(*[Q(game=game) for game in games], join_type="OR")
        accounts = await models.HoyoAccount.filter(game_query, user_id=user_id).all()
        accounts = [account for account in accounts if account.platform in platforms]
        if not accounts:
            raise NoAccountFoundError(games, platforms)

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
        # Update enka.py assets
        async with enka.GenshinClient() as api:
            await api.update_assets()

        async with enka.HSRClient() as api:
            await api.update_assets()

        # Update genshin.py assets
        await genshin.utility.update_characters_any()

        # Update item ID -> name mappings
        await self.update_zzz_item_id_name_map()
        await self.update_hsr_item_id_name_map()

    async def update_zzz_item_id_name_map(self) -> None:
        result: dict[str, dict[str, str]] = {}

        async with asyncio.TaskGroup() as tg:
            item_temp_task = tg.create_task(fetch_json(self.session, ZZZ_ITEM_TEMPLATE_URL))
            avatar_temp_task = tg.create_task(fetch_json(self.session, ZZZ_AVATAR_TEMPLATE_URL))
            text_map_tasks = {
                lang: tg.create_task(fetch_json(self.session, ZZZ_TEXT_MAP_URL.format(lang=lang)))
                for lang in ZENLESS_DATA_LANGS
            }

        item_template = item_temp_task.result()
        avatar_template = avatar_temp_task.result()
        text_maps = {lang: task.result() for lang, task in text_map_tasks.items()}

        item_id_mapping: dict[int, str] = {}  # item ID -> text map key

        for item in item_template["KHHABHLHAFG"]:
            if any(keyword in item["EAAFCGPDFAA"] for keyword in ("Bangboo_Name", "Item_Weapon")):
                item_id_mapping[item["NGPCCDGBLLK"]] = item["EAAFCGPDFAA"]

        for avatar in avatar_template["KHHABHLHAFG"]:
            item_id_mapping[avatar["NGPCCDGBLLK"]] = avatar["EAAFCGPDFAA"]

        for lang, text_map in text_maps.items():
            result[lang] = {
                str(item_id): text_map.get(text_map_key, "")
                for item_id, text_map_key in item_id_mapping.items()
            }

        for lang, text_map in result.items():
            await models.JSONFile.write(f"zzz_item_names_{lang}.json", text_map)

    async def update_hsr_item_id_name_map(self) -> None:
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
        if isinstance(exception, commands.CommandNotFound):
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
                embed = client.get_daily_reward_embed(reward, locale, self.translator, blur=True)
            else:
                await client.verify_mmt(genshin.models.MMTResult(**user.temp_data))
                embed = DefaultEmbed(
                    locale, self.translator, title=LocaleStr(key="geeetest_verification_complete")
                )

            await message.edit(embed=embed, view=None)
        except Exception as e:
            embed, recognized = get_error_embed(e, locale, self.translator)
            if not recognized:
                self.capture_exception(e)
            await message.edit(embed=embed, view=None)

    async def close(self) -> None:
        logger.info("Bot shutting down...")
        if self.geetest_command_task is not None:
            self.geetest_command_task.cancel()

        self.executor.shutdown()
        await super().close()
