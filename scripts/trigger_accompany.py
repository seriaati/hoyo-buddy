"""Manually trigger the character accompany check-in task for testing.

Usage:
    uv run scripts/trigger_accompany.py [--uid UID]

Without --uid: runs the full AccompanyCheckin.execute(), honoring all queue
filters (HoYoLAB + Genshin/HSR/ZZZ, accompany_checkin enabled, a character
selected, and not already run today in UTC+8), then prints the accompany
embeds it created.

With --uid: directly calls AccompanyCheckin._accompany() on that single
account, bypassing the queue filters so it can be re-run freely, and prints
the resulting embed.

The task writes results to the discordembed table; the actual DM is sent
later by EmbedSender on the bot process.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Parse our own args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_parser = argparse.ArgumentParser(description="Trigger the accompany check-in task")
_parser.add_argument(
    "--uid", type=int, default=None, help="Run for a single account by UID, bypassing queue filters"
)
_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.db import HoyoAccount
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.db.pgsql import Database
from hoyo_buddy.hoyo.auto_tasks.accompany_checkin import AccompanyCheckin
from hoyo_buddy.l10n import translator


async def main() -> None:
    async with Database(), translator:
        if _args.uid is None:
            logger.info("Running full AccompanyCheckin.execute()")
            await AccompanyCheckin.execute()
            embeds = await DiscordEmbed.filter(task_type="accompany")
            logger.info(f"{len(embeds)} accompany embed(s) pending DM via EmbedSender")
            for embed in embeds:
                logger.info(
                    f"  [{embed.type}] {embed.data.get('title')!r} -> "
                    f"{embed.data.get('description')!r}"
                )
            return

        account = await HoyoAccount.get_or_none(uid=_args.uid).prefetch_related(
            "user", "user__settings"
        )
        if account is None:
            logger.error(f"No account found with uid={_args.uid}")
            return

        logger.info(
            f"Direct accompany for {account} | game={account.game} region={account.region} "
            f"role_id={account.accompany_role_id}"
        )
        embed = await AccompanyCheckin._accompany(account)  # noqa: SLF001
        if embed is None:
            logger.info("Already accompanied today or no points gained, no notification")
        else:
            logger.info(f"Result embed: {embed.to_dict()}")


if __name__ == "__main__":
    asyncio.run(main())
