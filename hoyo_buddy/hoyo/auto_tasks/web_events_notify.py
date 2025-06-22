from __future__ import annotations

import asyncio
import itertools
from typing import TYPE_CHECKING, ClassVar

import genshin
from loguru import logger

from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME
from hoyo_buddy.db.models import HoyoAccount, JSONFile
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.hoyo.web_events import WebEventsView

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.enums import Game


class WebEventsNotify:
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _bot: ClassVar[HoyoBuddy]
    _notify_count: ClassVar[int]

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            return

        async with cls._lock:
            start = asyncio.get_event_loop().time()

            try:
                logger.info("Web events notify started")

                cls._bot = bot
                cls._notify_count = 0

                accounts = await HoyoAccount.filter(notif_settings__web_events=True)
                games = {account.game for account in accounts}

                for game in games:
                    try:
                        now_events = await cls.fetch_events(game)
                    except Exception as e:
                        cls._bot.capture_exception(e)
                        continue

                    saved_events: list[genshin.models.WebEvent] = [
                        genshin.models.WebEvent(**event)
                        for event in (
                            await JSONFile.read(f"web_events_{game.value}.json", default=[])
                        )
                    ]
                    if not saved_events:
                        saved_events = now_events

                    saved_event_ids = {event.id for event in saved_events}
                    notify_events: list[genshin.models.WebEvent] = [
                        event for event in now_events if event.id not in saved_event_ids
                    ]
                    if not notify_events:
                        continue

                    notify_accounts = [account for account in accounts if account.game == game]
                    for account in notify_accounts:
                        await cls.notify_events(account, notify_events)
                        cls._notify_count += 1
            except Exception as e:
                cls._bot.capture_exception(e)
            finally:
                logger.info(f"Web events notify finished, notified {cls._notify_count} accounts")
                logger.info(
                    f"Web events notify took {asyncio.get_event_loop().time() - start:.2f}s"
                )

    @classmethod
    async def fetch_events(cls, game: Game) -> list[genshin.models.WebEvent]:
        client = genshin.Client(game=HB_GAME_TO_GPY_GAME[game])
        return await client.get_web_events()

    @classmethod
    async def notify_events(
        cls, account: HoyoAccount, events: list[genshin.models.WebEvent]
    ) -> None:
        await account.fetch_related("user", "user__settings")
        locale = account.user.settings.locale or Locale.american_english
        embeds = [
            WebEventsView.get_event_embed(event, locale).set_footer(
                text=LocaleStr(key="web_events_embed_footer")
            )
            for event in events
        ]

        for chunk in itertools.batched(embeds, 10):
            await cls._bot.dm_user(account.user.id, embeds=chunk)
