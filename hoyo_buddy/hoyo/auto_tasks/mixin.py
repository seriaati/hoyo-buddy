from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import tortoise.timezone
from loguru import logger
from tortoise.expressions import Case, Q, When

from hoyo_buddy.constants import (
    AUTO_TASK_INTERVALS,
    AUTO_TASK_LAST_TIME_FIELDS,
    AUTO_TASK_TOGGLE_FIELDS,
    UTC_8,
)
from hoyo_buddy.db import models
from hoyo_buddy.db.utils import build_account_query
from hoyo_buddy.enums import Game
from hoyo_buddy.utils import get_now

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.types import AutoTaskType


class AutoTaskMixin:
    @staticmethod
    async def build_auto_task_queue(
        task_type: AutoTaskType,
        *,
        games: Sequence[Game] | None = None,
        region: genshin.Region | None = None,
    ) -> asyncio.Queue[models.HoyoAccount]:
        games = games or list(Game)
        query = build_account_query(games=games, region=region)

        # Tasks that reset once per day (UTC+8) instead of running on a fixed interval
        daily_task = task_type in {"checkin", "accompany"}

        # Auto task exclusions
        if not daily_task:
            # Interval based auto tasks
            interval = AUTO_TASK_INTERVALS.get(task_type)
            if interval is None:
                logger.error(f"{task_type!r} missing in AUTO_TASK_INTERVALS")
            else:
                field_name = AUTO_TASK_LAST_TIME_FIELDS.get(task_type)
                if field_name is None:
                    logger.error(f"{task_type!r} missing in AUTO_TASK_LAST_TIME_FIELDS")
                else:
                    # Filter accounts that haven't been processed in the last interval or have never been processed
                    threshold_time = tortoise.timezone.now() - datetime.timedelta(seconds=interval)
                    query &= Q(
                        **{f"{field_name}__lt": threshold_time, f"{field_name}__isnull": True},
                        join_type="OR",
                    )

        # Filter accounts that have the auto task toggle enabled
        toggle_field = AUTO_TASK_TOGGLE_FIELDS.get(task_type)
        if toggle_field is None:
            logger.error(f"{task_type!r} missing in AUTO_TASK_TOGGLE_FIELDS")
        else:
            query &= Q(**{toggle_field: True}, join_type="AND")

        # Mimo-task: Only process accounts that haven't claimed all rewards (mimo_all_claimed_time is null)
        if task_type == "mimo_task":
            query &= Q(mimo_all_claimed_time__isnull=True)

        # Redeem-specific: Only process accounts that can redeem codes
        if task_type == "redeem":
            query &= Q(cookies__contains="cookie_token_v2") | (
                Q(cookies__contains="ltmid_v2") & Q(cookies__contains="stoken")
            )

        # Accompany-specific: Only process accounts that have a character selected
        if task_type == "accompany":
            query &= Q(accompany_role_id__isnull=False)

        # Supporters have priority
        supporter_ids: list[int] = await models.JSONFile.read("supporter_ids.json", default=[])
        logger.debug(f"Supporter IDs: {supporter_ids}")
        query_set = (
            models.HoyoAccount.filter(query)
            .annotate(is_supporter=Case(When(user_id__in=supporter_ids, then="1"), default="0"))
            .order_by("-is_supporter", "id")
        )

        last_time_field = AUTO_TASK_LAST_TIME_FIELDS.get(task_type)

        queue: asyncio.Queue[models.HoyoAccount] = asyncio.Queue()
        cookie_game_pairs: set[tuple[str, Game]] = set()
        async for account in query_set:
            # For daily tasks: skip accounts with the same cookies and game (duplicates),
            # and skip accounts that already ran today (UTC+8)
            if daily_task:
                last_time = getattr(account, last_time_field) if last_time_field else None
                if (account.cookies, account.game) in cookie_game_pairs or (
                    last_time is not None and last_time.astimezone(UTC_8).date() == get_now().date()
                ):
                    continue

            cookie_game_pairs.add((account.cookies, account.game))
            await queue.put(account)

        return queue
