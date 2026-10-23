from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import (
    AUTO_GACHA_IMPORT_SUPPORT_GAMES,
    CONCURRENT_TASK_NUM,
    MAX_PROXY_ERROR_NUM,
)
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.auto_tasks.mixin import AutoTaskMixin
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.hoyo.gacha_import import (
    UnknownGachaItemError,
    fetch_authkey,
    fetch_genshin_records,
    fetch_zzz_chronicle_records,
    save_records,
)
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import capture_exception, error_handler, get_now, sleep

if TYPE_CHECKING:
    import aiohttp
    import asyncpg

    from hoyo_buddy.db import GachaHistory, HoyoAccount
    from hoyo_buddy.embeds import ErrorEmbed


class AutoGachaImport(AutoTaskMixin):
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _count: ClassVar[int]
    _error_counts: ClassVar[defaultdict[int, int]]
    _session: ClassVar[aiohttp.ClientSession]
    _pool: ClassVar[asyncpg.Pool]
    _item_ids: ClassVar[dict[str, int] | None]
    _item_ids_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, session: aiohttp.ClientSession, pool: asyncpg.Pool) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                cls._count = 0
                cls._error_counts = defaultdict(int)
                cls._session = session
                cls._pool = pool
                cls._item_ids = None

                queue = await cls.build_auto_task_queue(
                    "gacha_import",
                    games=list(AUTO_GACHA_IMPORT_SUPPORT_GAMES),
                    region=genshin.Region.OVERSEAS,
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._gacha_import_task(queue))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                capture_exception(e)
            else:
                logger.info(f"{cls.__name__} finished, count={cls._count}")
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )

    @classmethod
    async def _get_item_ids(cls) -> dict[str, int]:
        """Get the English item name to ID map, fetched once per run."""
        async with cls._item_ids_lock:
            if cls._item_ids is None:
                ambr = AmbrAPIClient(session=cls._session)
                id_to_name = await ambr.fetch_item_id_to_name_map()
                cls._item_ids = {name: id_ for id_, name in id_to_name.items()}
            return cls._item_ids

    @classmethod
    async def _gacha_import_task(cls, queue: asyncio.Queue[HoyoAccount]) -> None:
        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")

            try:
                await account.fetch_related("user", "user__settings")
                embed = await cls._gacha_import(account)
            except Exception as e:
                with error_handler():
                    if cls._error_counts[account.id] >= MAX_PROXY_ERROR_NUM:
                        locale = account.user.settings.locale or Locale.american_english
                        embed, _ = get_error_embed(e, locale)
                        embed.add_acc_info(account, blur=False)
                        await DiscordEmbed.create(
                            embed,
                            user_id=account.user.id,
                            account_id=account.id,
                            task_type="gacha_import",
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        capture_exception(e)
                        await queue.put(account)
            else:
                if embed is not None:
                    cls._count += 1
                    await DiscordEmbed.create(
                        embed,
                        user_id=account.user.id,
                        account_id=account.id,
                        task_type="gacha_import",
                    )

                account.last_gacha_import_time = get_now()
                await account.save(update_fields=("last_gacha_import_time",))
            finally:
                await sleep("gacha_import")
                queue.task_done()

    @classmethod
    async def _fetch_records(
        cls, account: HoyoAccount, cursors: dict[str, int]
    ) -> list[GachaHistory]:
        client = account.client
        client.use_proxy = True

        if account.game is Game.GENSHIN:
            authkey = await fetch_authkey(client, account)
            return await fetch_genshin_records(
                client,
                account,
                authkey=authkey,
                cursors=cursors,
                item_ids=await cls._get_item_ids(),
            )
        return await fetch_zzz_chronicle_records(client, account, cursors=cursors)

    @classmethod
    async def _gacha_import(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english
        cursors = dict(account.gacha_cursors)

        try:
            records = await cls._fetch_records(account, cursors)
            count = await save_records(account, records, cursors=cursors, pool=cls._pool)
        except UnknownGachaItemError as e:
            # Item data isn't updated yet (e.g. on new version release), retry in the next run
            logger.warning(f"{cls.__name__} skipped {account}: {e}")
            return None
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed

        if count == 0:
            return None

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(key="gacha_import_success_title"),
            description=LocaleStr(key="gacha_import_success_message", count=count),
        )
        embed.set_footer(text=LocaleStr(key="auto_gacha_import_footer"))
        return embed.add_acc_info(account, blur=False)
