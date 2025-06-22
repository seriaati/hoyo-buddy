from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, Literal

import genshin
from loguru import logger
from seria.utils import create_bullet_list

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import CONCURRENT_TASK_NUM, HB_GAME_TO_GPY_GAME, MAX_PROXY_ERROR_NUM
from hoyo_buddy.db.models import DiscordEmbed
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.emojis import MIMO_POINT_EMOJIS
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import (
    convert_code_to_redeem_url,
    error_handler,
    get_mimo_task_str,
    get_now,
    sleep,
)

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import AutoTaskType

SUPPORT_GAMES = (Game.STARRAIL, Game.ZZZ, Game.GENSHIN)


class AutoMimo:
    _bot: ClassVar[HoyoBuddy]
    _mimo_game_data: ClassVar[dict[Game, tuple[int, int]]]
    _down_games: ClassVar[set[Game]]
    _error_counts: ClassVar[defaultdict[int, int]]

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
    async def _auto_mimo_task(
        cls, queue: asyncio.Queue[HoyoAccount], *, task_type: Literal["task", "buy", "draw"]
    ) -> None:
        while True:
            account = await queue.get()
            logger.debug(f"{cls.__name__} is processing account {account}")

            if account.game in cls._down_games:
                logger.debug(f"Skipping account {account} because {account.game} is down")
                queue.task_done()
                continue

            await account.fetch_related("user", "user__settings")

            notif_task_type: AutoTaskType | None = None
            try:
                account.client.use_proxy = True
                if task_type == "task":
                    notif_task_type = "mimo_task"
                    embed = await cls._complete_mimo_tasks(account)
                    last_time_attr = "last_mimo_task_time"
                elif task_type == "buy":
                    notif_task_type = "mimo_buy"
                    last_time_attr = "last_mimo_buy_time"
                    embed = await cls._buy_mimo_valuables(account)
                elif task_type == "draw":
                    notif_task_type = "mimo_draw"
                    last_time_attr = "last_mimo_draw_time"
                    embed = await cls._draw_lottery(account)
            except Exception as e:
                with error_handler():
                    if (
                        cls._error_counts[account.id] >= MAX_PROXY_ERROR_NUM
                        and notif_task_type is not None
                    ):
                        locale = account.user.settings.locale or Locale.american_english
                        embed, _ = get_error_embed(e, locale)
                        embed.add_acc_info(account, blur=False)
                        await DiscordEmbed.create(
                            embed,
                            user_id=account.user.id,
                            account_id=account.id,
                            task_type=notif_task_type,
                        )
                    else:
                        cls._error_counts[account.id] += 1
                        cls._bot.capture_exception(e)
                        await queue.put(account)
            else:
                # Set last completion time
                logger.debug(
                    f"Setting last time for {account}, last_time_attr={last_time_attr}, now={get_now()}"
                )
                setattr(account, last_time_attr, get_now())
                await account.save(update_fields=(last_time_attr,))

                if embed is not None:
                    embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
                    embed.add_acc_info(account, blur=False)

                    await DiscordEmbed.create(
                        embed,
                        user_id=account.user.id,
                        account_id=account.id,
                        task_type=notif_task_type,
                    )
            finally:
                await sleep("mimo_task")
                queue.task_done()

    @classmethod
    async def _complete_mimo_tasks(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english

        try:
            client = account.client
            client.set_lang(locale)

            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            result = await client.finish_and_claim_mimo_tasks(
                game_id=game_id, version_id=version_id
            )
            if result.all_claimed:
                account.mimo_all_claimed_time = get_now()
                await account.save(update_fields=("mimo_all_claimed_time",))

            if len(result.finished) == 0 and result.claimed_points == 0:
                return None

            embed = DefaultEmbed(
                locale,
                title=LocaleStr(
                    custom_str="{mimo_title} {label}",
                    mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                    label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
                ),
                description=LocaleStr(
                    key="mimo_auto_task_embed_desc",
                    finish=len(result.finished),
                    claim_point=result.claimed_points,
                ),
            )
            embed.add_description(
                f"{create_bullet_list([get_mimo_task_str(task, account.game) for task in result.finished])}"
            )
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed

    @classmethod
    async def _buy_mimo_valuables(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english

        try:
            client = account.client
            client.set_lang(locale)

            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            bought = await client.buy_mimo_valuables(game_id=game_id, version_id=version_id)

            if not bought:
                return None

            mimo_point_emoji = MIMO_POINT_EMOJIS[account.game]
            bought_strs: list[str] = []
            for item, code in bought:
                bought_str = f"{item.name} - {item.cost} {mimo_point_emoji}"
                success = False
                if account.can_redeem_code:
                    _, success = await client.redeem_code(code, locale=locale)

                if not success:
                    bought_str += f" ({convert_code_to_redeem_url(code, game=account.game)})"
                bought_strs.append(bought_str)

                await sleep("redeem")

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
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed

    @classmethod
    async def _draw_lottery(cls, account: HoyoAccount) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or Locale.american_english

        try:
            client = account.client
            client.set_lang(locale)

            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            info = await client.get_mimo_lottery_info(game_id=game_id, version_id=version_id)
            count = info.limit_count - info.current_count
            point = info.current_point
            if count == 0 or point < info.cost:
                return None

            results: list[genshin.models.MimoLotteryResult] = []

            for _ in range(count):
                if point < info.cost:
                    break

                try:
                    result = await client.draw_mimo_lottery(game_id=game_id, version_id=version_id)
                    await sleep("mimo_lottery")
                except genshin.GenshinException as e:
                    if e.retcode == -510001:  # Invalid fields in calculation
                        break
                    raise

                results.append(result)
                point -= info.cost

            item_strs: list[str] = []

            for result in results:
                item_str = result.reward.name

                if result.code:
                    success = False
                    if account.can_redeem_code:
                        _, success = await client.redeem_code(result.code, locale=locale)
                        await sleep("redeem")

                    if not success:
                        item_str += (
                            f" ({convert_code_to_redeem_url(result.code, game=account.game)})"
                        )

                item_strs.append(item_str)

            if not item_strs:
                return None

            embed = DefaultEmbed(
                locale,
                title=LocaleStr(
                    custom_str="{mimo_title} {label}",
                    mimo_title=LocaleStr(key="point_detail_tag_mimo", mi18n_game="mimo"),
                    label=LocaleStr(key="mimo_auto_draw_button_label"),
                ),
                description=LocaleStr(
                    key="mimo_auto_draw_embed_desc",
                    points=sum(info.cost for _ in range(len(item_strs))),
                ),
            )
            embed.add_description(f"{create_bullet_list(item_strs)}")
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed


class AutoMimoTask(AutoMimo):
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        start = asyncio.get_event_loop().time()

        async with cls._lock:
            try:
                cls._bot = bot
                cls._mimo_game_data = {}
                cls._down_games = set()
                cls._error_counts = defaultdict(int)

                # Auto task
                queue = await cls._bot.build_auto_task_queue(
                    "mimo_task", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, task_type="task"))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            else:
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )


class AutoMimoBuy(AutoMimo):
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        start = asyncio.get_event_loop().time()

        async with cls._lock:
            try:
                cls._bot = bot
                cls._mimo_game_data = {}
                cls._down_games = set()
                cls._error_counts = defaultdict(int)

                # Auto buy
                queue = await cls._bot.build_auto_task_queue(
                    "mimo_buy", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, task_type="buy"))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            else:
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )


class AutoMimoDraw(AutoMimo):
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.debug(f"{cls.__name__} is already running")
            return

        start = asyncio.get_event_loop().time()

        async with cls._lock:
            try:
                cls._bot = bot
                cls._mimo_game_data = {}
                cls._down_games = set()
                cls._error_counts = defaultdict(int)

                # Auto draw
                queue = await cls._bot.build_auto_task_queue(
                    "mimo_draw", games=SUPPORT_GAMES, region=genshin.Region.OVERSEAS
                )
                if queue.empty():
                    logger.debug(f"Queue is empty for {cls.__name__}")
                    return

                logger.info(f"Starting {cls.__name__} for {queue.qsize()} accounts")
                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, task_type="draw"))
                    for _ in range(CONCURRENT_TASK_NUM)
                ]

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            else:
                logger.info(
                    f"{cls.__name__} took {asyncio.get_event_loop().time() - start:.2f} seconds"
                )
