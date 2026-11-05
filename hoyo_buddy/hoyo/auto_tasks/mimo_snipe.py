from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, ClassVar

import genshin
from loguru import logger

from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME, MIMO_SUPPORT_GAMES
from hoyo_buddy.db.models import DiscordEmbed, HoyoAccount, JSONFile
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.auto_tasks.auto_mimo import AutoMimoMixin, is_mimo_item_obtainable
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import capture_exception, get_now

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from hoyo_buddy.enums import Game

PREPARE_LEAD = datetime.timedelta(seconds=60)
"""How long before the restock to fetch each account's points and items."""
FIRE_LEAD = datetime.timedelta(seconds=1)
"""How long before the restock to start sending buy requests."""
SNIPE_DURATION = datetime.timedelta(seconds=30)
"""How long after the restock to keep retrying out of stock items."""


class MimoRestockSnipe(AutoMimoMixin):
    """Buy mimo shop currency items for sponsors the moment they restock."""

    _scheduled: ClassVar[dict[Game, datetime.datetime]] = {}

    @staticmethod
    async def _get_accounts(game: Game) -> list[HoyoAccount]:
        supporter_ids: list[int] = await JSONFile.read("supporter_ids.json", default=[])
        if not supporter_ids:
            return []

        accounts = await HoyoAccount.filter(
            game=game, region=genshin.Region.OVERSEAS, mimo_auto_buy=True, user_id__in=supporter_ids
        ).prefetch_related("user", "user__settings")

        # Skip accounts with the same cookies (duplicates)
        unique: dict[str, HoyoAccount] = {}
        for account in accounts:
            unique.setdefault(account.cookies, account)
        return list(unique.values())

    @staticmethod
    async def _get_restock_time(account: HoyoAccount) -> datetime.datetime | None:
        client = account.client
        client.use_proxy = True

        try:
            game_id, version_id = await client._get_mimo_game_data(
                HB_GAME_TO_GPY_GAME[account.game]
            )
        except ValueError:
            # The game has no Traveling Mimo event running
            return None

        items = await client.get_mimo_valuables(game_id=game_id, version_id=version_id)
        refresh_times = [
            item.next_refresh_time
            for item in items
            if item.next_refresh_time > datetime.timedelta(0)
        ]
        if not refresh_times:
            return None

        # Restocks happen on the minute, round off the request latency
        restock_at = get_now() + min(refresh_times) + datetime.timedelta(seconds=30)
        return restock_at.replace(second=0, microsecond=0)

    @classmethod
    async def schedule(cls, scheduler: AsyncIOScheduler) -> None:
        """Schedule a snipe job before the next restock of each game."""
        for game in MIMO_SUPPORT_GAMES:
            try:
                await cls._schedule_game(scheduler, game)
            except Exception as e:
                capture_exception(e)

    @classmethod
    async def _schedule_game(cls, scheduler: AsyncIOScheduler, game: Game) -> None:
        accounts = await cls._get_accounts(game)
        if not accounts:
            return

        restock_at = await cls._get_restock_time(accounts[0])
        if restock_at is None or cls._scheduled.get(game) == restock_at:
            return

        scheduler.add_job(
            cls.execute,
            "date",
            run_date=max(restock_at - PREPARE_LEAD, get_now()),
            args=(game, restock_at),
            id=f"mimo_snipe_{game.name}",
            replace_existing=True,
        )
        cls._scheduled[game] = restock_at
        logger.info(f"Scheduled {game} mimo restock snipe at {restock_at}")

    @classmethod
    async def execute(cls, game: Game, restock_at: datetime.datetime) -> None:
        accounts = await cls._get_accounts(game)
        if not accounts:
            return

        logger.info(f"Sniping {game} mimo restock at {restock_at} for {len(accounts)} accounts")

        try:
            game_id, version_id = await accounts[0].client._get_mimo_game_data(
                HB_GAME_TO_GPY_GAME[game]
            )
        except Exception as e:
            capture_exception(e)
            return

        results = await asyncio.gather(
            *(cls._snipe(account, game_id, version_id, restock_at) for account in accounts),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                capture_exception(result)

    @classmethod
    async def _snipe(
        cls, account: HoyoAccount, game_id: int, version_id: int, restock_at: datetime.datetime
    ) -> None:
        locale = account.user.settings.locale or Locale.american_english
        client = account.client
        client.use_proxy = True
        client.set_lang(locale)

        points = await client.get_mimo_point_count()
        items = await client.get_mimo_valuables(game_id=game_id, version_id=version_id)
        targets = [item for item in items if is_mimo_item_obtainable(item) and item.cost <= points]
        if not targets:
            return

        await asyncio.sleep(max(0, (restock_at - FIRE_LEAD - get_now()).total_seconds()))
        bought = await client.snipe_mimo_valuables(
            targets,
            game_id=game_id,
            version_id=version_id,
            points=points,
            deadline=restock_at + SNIPE_DURATION,
        )
        if not bought:
            return

        account.last_mimo_buy_time = get_now()
        await account.save(update_fields=("last_mimo_buy_time",))

        embed = await cls._get_buy_embed(account, bought, locale)
        embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
        embed.add_acc_info(account, blur=False)
        await DiscordEmbed.create(
            embed, user_id=account.user.id, account_id=account.id, task_type="mimo_buy"
        )
