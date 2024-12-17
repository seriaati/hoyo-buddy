from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
from loguru import logger
from seria.utils import create_bullet_list
from tortoise.expressions import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME, PROXY_APIS
from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.embeds import DefaultEmbed, Embed, ErrorEmbed
from hoyo_buddy.emojis import MIMO_POINT_EMOJIS
from hoyo_buddy.enums import Game, Platform
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_mimo_task_str

if TYPE_CHECKING:
    import genshin

    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import ProxyAPI

API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10
SLEEP_TIME = 2.5


class AutoMimo:
    _task_count: ClassVar[int]
    _buy_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _mimo_game_data: ClassVar[dict[Game, tuple[int, int]]]
    _down_games: ClassVar[set[Game]]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            return

        start = asyncio.get_event_loop().time()
        async with cls._lock:
            try:
                logger.info("Auto mimo task started")

                cls._task_count = 0
                cls._buy_count = 0
                cls._bot = bot
                cls._mimo_game_data = {}
                cls._down_games = set()

                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                accounts = await HoyoAccount.filter(
                    Q(game=Game.STARRAIL) | Q(game=Game.ZZZ),
                    Q(mimo_auto_task=True) | Q(mimo_auto_buy=True),
                )

                for account in accounts:
                    if account.platform is Platform.MIYOUSHE:
                        continue
                    await queue.put(account)

                tasks = [asyncio.create_task(cls._mimo_task(queue, api)) for api in PROXY_APIS]
                tasks.append(asyncio.create_task(cls._mimo_task(queue, "LOCAL")))

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            finally:
                logger.info(
                    f"Mimo auto task finished, {cls._task_count} tasks and {cls._buy_count} buys"
                )

        end = asyncio.get_event_loop().time()
        logger.info(f"Auto mimo task took {end - start:.2f} seconds")

    @classmethod
    async def _get_mimo_game_data(cls, client: genshin.Client, game: Game) -> tuple[int, int]:
        try:
            game_id, version_id = await client._get_mimo_game_data(HB_GAME_TO_GPY_GAME[game])
        except ValueError:
            logger.warning(f"Failed to get mimo game data for {game}")
            cls._down_games.add(game)
            raise

        cls._mimo_game_data[game] = (game_id, version_id)
        return game_id, version_id

    @classmethod
    async def _mimo_task(
        cls, queue: asyncio.Queue[HoyoAccount], api_name: ProxyAPI | Literal["LOCAL"]
    ) -> None:
        logger.info(f"Mimo task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            # test if the api is working
            async with bot.session.get(PROXY_APIS[api_name]) as resp:
                if resp.status != 200:
                    msg = f"API {api_name} returned {resp.status}"
                    raise RuntimeError(msg)

        api_error_count = 0

        while True:
            account = await queue.get()
            if account.game in cls._down_games:
                queue.task_done()
                continue

            await account.fetch_related("user", "user__settings", "notif_settings")

            task_embed = None
            valuable_embed = None

            try:
                if account.mimo_auto_task:
                    task_embed = await cls._complete_mimo_tasks(api_name, account)
                if account.mimo_auto_buy:
                    await asyncio.sleep(SLEEP_TIME)
                    valuable_embed = await cls._buy_mimo_valuables(api_name, account)
            except Exception as e:
                await queue.put(account)
                api_error_count += 1

                logger.warning(f"Mimo auto task failed for {account}")
                cls._bot.capture_exception(e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Proxy API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                if task_embed is not None:
                    cls._task_count += 1

                    task_embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
                    task_embed.add_acc_info(account)

                    if isinstance(task_embed, ErrorEmbed):
                        account.mimo_auto_task = False
                        await account.save(update_fields=("mimo_auto_task",))
                        content = LocaleStr(key="mimo_auto_task_error_dm_content").translate(
                            account.user.settings.locale or discord.Locale.american_english
                        )
                    else:
                        content = None

                    if (
                        isinstance(task_embed, DefaultEmbed)
                        and account.notif_settings.mimo_task_success
                    ) or (
                        isinstance(task_embed, ErrorEmbed)
                        and account.notif_settings.mimo_task_failure
                    ):
                        await cls._bot.dm_user(account.user.id, embed=task_embed, content=content)

                if valuable_embed is not None:
                    cls._buy_count += 1

                    valuable_embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
                    valuable_embed.add_acc_info(account)

                    if isinstance(valuable_embed, ErrorEmbed):
                        account.mimo_auto_task = False
                        await account.save(update_fields=("mimo_auto_task",))
                        content = LocaleStr(key="mimo_auto_buy_error_dm_content").translate(
                            account.user.settings.locale or discord.Locale.american_english
                        )
                    else:
                        content = None

                    if (
                        isinstance(task_embed, DefaultEmbed)
                        and account.notif_settings.mimo_buy_success
                    ) or (
                        isinstance(task_embed, ErrorEmbed)
                        and account.notif_settings.mimo_buy_failure
                    ):
                        await cls._bot.dm_user(
                            account.user.id, embed=valuable_embed, content=content
                        )

            finally:
                await asyncio.sleep(SLEEP_TIME)
                queue.task_done()

    @classmethod
    async def _complete_mimo_tasks(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> Embed | None:
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        try:
            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            finished, claimed = await client.finish_and_claim_mimo_tasks(
                game_id=game_id,
                version_id=version_id,
                api_url=api_name if api_name == "LOCAL" else PROXY_APIS[api_name],
            )
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)
            return embed

        if len(finished) == 0 and len(claimed) == 0:
            return None

        finished_ids = {task.id for task in finished}
        tasks = finished + [task for task in claimed if task.id not in finished_ids]

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(
                custom_str="{mimo_title} {label}",
                mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            ),
            description=LocaleStr(
                key="mimo_auto_task_embed_desc",
                finish=len(finished),
                claim_point=sum(task.point for task in claimed),
            ),
        )
        embed.add_description(
            f"{create_bullet_list([get_mimo_task_str(task, account.game) for task in tasks])}"
        )
        return embed

    @classmethod
    async def _buy_mimo_valuables(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> Embed | None:
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)
        api_url = api_name if api_name == "LOCAL" else PROXY_APIS[api_name]

        try:
            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            bought = await client.buy_mimo_valuables(
                game_id=game_id, version_id=version_id, api_url=api_url
            )
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                cls._bot.capture_exception(e)
            return embed

        if len(bought) == 0:
            return None

        mimo_point_emoji = MIMO_POINT_EMOJIS[account.game]
        bought_strs: list[str] = []
        for item, code in bought:
            bought_str = f"{item.name} ({item.cost} {mimo_point_emoji})"
            _, success = await client.redeem_code(code, locale=locale, api_url=api_url)
            if not success:
                bought_str += f": {code}"
            bought_strs.append(bought_str)

            await asyncio.sleep(6)

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(
                custom_str="{mimo_title} {label}",
                mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                label=LocaleStr(key="mimo_auto_buy_button_label"),
            ),
            description=LocaleStr(
                key="mimo_auto_buy_embed_desc",
                item=len(bought),
                points=sum(item.cost for item in [b[0] for b in bought]),
            ),
        )
        embed.add_description(f"{create_bullet_list(bought_strs)}")
        return embed
