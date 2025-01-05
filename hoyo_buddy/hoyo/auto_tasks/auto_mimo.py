from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger
from seria.utils import create_bullet_list
from tortoise.expressions import Q

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME, PROXY_APIS
from hoyo_buddy.db import HoyoAccount
from hoyo_buddy.db.models import TaskLeftover
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed
from hoyo_buddy.emojis import MIMO_POINT_EMOJIS
from hoyo_buddy.enums import AutoTaskType, Game, Platform
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import convert_code_to_redeem_url, get_mimo_task_str, get_now

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import ProxyAPI

MAX_API_ERROR_COUNT = 10
SLEEP_TIME = 2.5


class AutoMimo:
    _task_count: ClassVar[int]
    _buy_count: ClassVar[int]
    _draw_count: ClassVar[int]

    _bot: ClassVar[HoyoBuddy]
    _mimo_game_data: ClassVar[dict[Game, tuple[int, int]]]
    _down_games: ClassVar[set[Game]]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    _running_task_type: ClassVar[AutoTaskType | None]
    _total_accs: ClassVar[int]
    _finished_accs: ClassVar[int]
    _last_acc_id: ClassVar[int | None] = None

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            logger.warning("Auto mimo is already running")
            return

        start = asyncio.get_event_loop().time()

        async with cls._lock:
            try:
                logger.info("Auto mimo started")

                cls._bot = bot
                cls._mimo_game_data = {}
                cls._down_games = set()

                cls._task_count = 0
                cls._buy_count = 0
                cls._draw_count = 0

                cls._running_task_type = None
                cls._total_accs = 0
                cls._finished_accs = 0
                cls._last_acc_id = None

                # Accounts that have claimed all mimo tasks
                skip_ids = {
                    acc.id
                    for acc in await HoyoAccount.filter(Q(mimo_all_claimed_time__isnull=False))
                }

                # Auto task
                logger.info("Starting auto mimo tasks")
                leftover = await TaskLeftover.filter(task_type=AutoTaskType.AUTO_MIMO_TASK).first()
                if leftover is not None:
                    logger.info(
                        f"Resuming auto mimo tasks, last account id: {leftover.last_account_id}"
                    )
                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                auto_task_accs = await HoyoAccount.filter(
                    Q(game=Game.STARRAIL) | Q(game=Game.ZZZ) | Q(game=Game.GENSHIN),
                    mimo_auto_task=True,
                ).order_by("id")

                for account in auto_task_accs:
                    if (
                        account.platform is Platform.MIYOUSHE
                        or account.id in skip_ids
                        or (leftover is not None and account.id < leftover.last_account_id)
                    ):
                        continue
                    await queue.put(account)

                cls._running_task_type = AutoTaskType.AUTO_MIMO_TASK
                cls._total_accs = queue.qsize()
                cls._finished_accs = 0
                cls._last_acc_id = None

                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, api, task_type="task"))
                    for api in PROXY_APIS
                ]
                tasks.append(
                    asyncio.create_task(cls._auto_mimo_task(queue, "LOCAL", task_type="task"))
                )

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Auto mimo tasks finished, {cls._task_count} tasks")

                # Auto buy
                logger.info("Starting auto mimo buys")
                leftover = await TaskLeftover.filter(task_type=AutoTaskType.AUTO_MIMO_BUY).first()
                if leftover is not None:
                    logger.info(
                        f"Resuming auto mimo buys, last account id: {leftover.last_account_id}"
                    )
                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                auto_buy_accs = await HoyoAccount.filter(
                    Q(game=Game.STARRAIL) | Q(game=Game.ZZZ) | Q(game=Game.GENSHIN),
                    mimo_auto_buy=True,
                ).order_by("id")

                for account in auto_buy_accs:
                    if (
                        account.platform is Platform.MIYOUSHE
                        or account.game in cls._down_games
                        or account.id in skip_ids
                        or (leftover is not None and account.id < leftover.last_account_id)
                    ):
                        continue
                    await queue.put(account)

                cls._running_task_type = AutoTaskType.AUTO_MIMO_BUY
                cls._total_accs = queue.qsize()
                cls._finished_accs = 0
                cls._last_acc_id = None

                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, api, task_type="buy"))
                    for api in PROXY_APIS
                ]
                tasks.append(
                    asyncio.create_task(cls._auto_mimo_task(queue, "LOCAL", task_type="buy"))
                )

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Auto mimo buys finished, {cls._buy_count}")

                # Auto draw
                logger.info("Starting auto mimo draws")
                leftover = await TaskLeftover.filter(task_type=AutoTaskType.AUTO_MIMO_DRAW).first()
                if leftover is not None:
                    logger.info(
                        f"Resuming auto mimo draws, last account id: {leftover.last_account_id}"
                    )
                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                auto_draw_accs = await HoyoAccount.filter(
                    Q(game=Game.STARRAIL) | Q(game=Game.ZZZ) | Q(game=Game.GENSHIN),
                    mimo_auto_draw=True,
                ).order_by("id")

                for account in auto_draw_accs:
                    if (
                        account.platform is Platform.MIYOUSHE
                        or account.game in cls._down_games
                        or account.id in skip_ids
                        or (leftover is not None and account.id < leftover.last_account_id)
                    ):
                        continue
                    await queue.put(account)

                cls._running_task_type = AutoTaskType.AUTO_MIMO_DRAW
                cls._total_accs = queue.qsize()
                cls._finished_accs = 0
                cls._last_acc_id = None

                tasks = [
                    asyncio.create_task(cls._auto_mimo_task(queue, api, task_type="draw"))
                    for api in PROXY_APIS
                ]
                tasks.append(
                    asyncio.create_task(cls._auto_mimo_task(queue, "LOCAL", task_type="draw"))
                )

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Auto mimo draws finished, {cls._draw_count}")
            except Exception as e:
                bot.capture_exception(e)
            finally:
                if (
                    (cls._finished_accs == 0 or cls._finished_accs < cls._total_accs)
                    and cls._running_task_type is not None
                    and cls._last_acc_id is not None
                ):
                    logger.info(
                        f"Auto mimo partially finished, will resume next time. Task type: {cls._running_task_type!r}, total: {cls._total_accs}, finished: {cls._finished_accs}"
                    )
                    await TaskLeftover.create(
                        task_type=cls._running_task_type, last_account_id=cls._last_acc_id
                    )
                else:
                    logger.info(
                        f"Auto mimo finished, {cls._task_count} tasks, {cls._buy_count} buys, {cls._draw_count} draws"
                    )
                    logger.info(
                        f"Auto mimo took {asyncio.get_event_loop().time() - start:.2f} seconds"
                    )

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
        cls,
        queue: asyncio.Queue[HoyoAccount],
        api_name: ProxyAPI | Literal["LOCAL"],
        *,
        task_type: Literal["task", "buy", "draw"],
    ) -> None:
        logger.info(f"Auto mimo {task_type} task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            try:
                async with bot.session.get(PROXY_APIS[api_name]) as resp:
                    resp.raise_for_status()
            except Exception as e:
                logger.warning(f"Failed to connect to {api_name}")
                bot.capture_exception(e)

        api_error_count = 0

        while True:
            account = await queue.get()
            if account.game in cls._down_games:
                queue.task_done()
                cls._last_acc_id = account.id
                cls._finished_accs += 1
                continue

            await account.fetch_related("user", "user__settings", "notif_settings")

            try:
                if task_type == "task":
                    embed = await cls._complete_mimo_tasks(api_name, account)
                elif task_type == "buy":
                    embed = await cls._buy_mimo_valuables(api_name, account)
                elif task_type == "draw":
                    embed = await cls._draw_lottery(api_name, account)
            except Exception as e:
                api_error_count += 1
                await queue.put(account)
                bot.capture_exception(e)

                if api_error_count >= MAX_API_ERROR_COUNT:
                    logger.warning(f"API {api_name} failed for {api_error_count} accounts")
                    return
            else:
                if embed is not None:
                    if task_type == "task":
                        cls._task_count += 1
                        feature_key = "mimo_auto_finish_and_claim_button_label"
                        success_notif = account.notif_settings.mimo_task_success
                        failure_notif = account.notif_settings.mimo_task_failure
                    elif task_type == "buy":
                        cls._buy_count += 1
                        feature_key = "mimo_auto_buy_button_label"
                        success_notif = account.notif_settings.mimo_buy_success
                        failure_notif = account.notif_settings.mimo_buy_failure
                    elif task_type == "draw":
                        cls._draw_count += 1
                        feature_key = "mimo_auto_draw_button_label"
                        success_notif = account.notif_settings.mimo_draw_success
                        failure_notif = account.notif_settings.mimo_draw_failure

                    embed.set_footer(text=LocaleStr(key="mimo_auto_task_embed_footer"))
                    embed.add_acc_info(account)

                    if isinstance(embed, ErrorEmbed):
                        if task_type == "task":
                            account.mimo_auto_task = False
                            await account.save(update_fields=("mimo_auto_task",))
                        elif task_type == "buy":
                            account.mimo_auto_buy = False
                            await account.save(update_fields=("mimo_auto_buy",))
                        elif task_type == "draw":
                            account.mimo_auto_draw = False
                            await account.save(update_fields=("mimo_auto_draw",))

                        content = LocaleStr(
                            key="auto_task_error_dm_content",
                            feature=LocaleStr(
                                custom_str="{mimo_title} {label}",
                                mimo_title=LocaleStr(
                                    key="point_detail_tag_mimo", mi18n_game="mimo"
                                ),
                                label=LocaleStr(key=feature_key),
                            ),
                            command="</mimo>",
                        ).translate(account.user.settings.locale or discord.Locale.american_english)
                    else:
                        content = None

                    if (isinstance(embed, DefaultEmbed) and success_notif) or (
                        isinstance(embed, ErrorEmbed) and failure_notif
                    ):
                        await cls._bot.dm_user(account.user.id, embed=embed, content=content)
            finally:
                await asyncio.sleep(SLEEP_TIME)
                queue.task_done()
                cls._last_acc_id = account.id
                cls._finished_accs += 1

    @classmethod
    async def _complete_mimo_tasks(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or discord.Locale.american_english

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
                game_id=game_id,
                version_id=version_id,
                api_url=api_name if api_name == "LOCAL" else PROXY_APIS[api_name],
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
    async def _buy_mimo_valuables(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or discord.Locale.american_english

        try:
            client = account.client
            client.set_lang(locale)
            api_url = api_name if api_name == "LOCAL" else PROXY_APIS[api_name]

            game_id, version_id = cls._mimo_game_data.get(account.game, (None, None))
            if game_id is None or version_id is None:
                try:
                    game_id, version_id = await cls._get_mimo_game_data(client, account.game)
                except ValueError:
                    return None

            bought = await client.buy_mimo_valuables(
                game_id=game_id, version_id=version_id, api_url=api_url
            )

            if not bought:
                return None

            mimo_point_emoji = MIMO_POINT_EMOJIS[account.game]
            bought_strs: list[str] = []
            for item, code in bought:
                bought_str = f"{item.name} - {item.cost} {mimo_point_emoji}"
                success = False
                if account.can_redeem_code:
                    _, success = await client.redeem_code(code, locale=locale, api_url=api_url)

                if not success:
                    bought_str += f" ({convert_code_to_redeem_url(code, game=account.game)})"
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
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise
            embed.add_acc_info(account, blur=False)
            return embed
        else:
            return embed

    @classmethod
    async def _draw_lottery(
        cls, api_name: ProxyAPI | Literal["LOCAL"], account: HoyoAccount
    ) -> DefaultEmbed | ErrorEmbed | None:
        locale = account.user.settings.locale or discord.Locale.american_english

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
            except genshin.GenshinException as e:
                if e.retcode == -510001:  # Invalid fields in calculation
                    break
                raise

            results.append(result)
            point -= info.cost
            await asyncio.sleep(0.5)

        item_strs: list[str] = []

        for result in results:
            item_str = result.reward.name

            if result.code:
                success = False
                if account.can_redeem_code:
                    _, success = await client.redeem_code(
                        result.code, locale=locale, api_url=api_name
                    )
                    await asyncio.sleep(6)

                if not success:
                    item_strs += f" ({convert_code_to_redeem_url(result.code, game=account.game)})"

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
        return embed
