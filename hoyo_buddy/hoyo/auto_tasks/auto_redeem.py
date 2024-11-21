from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, ClassVar, Literal

import discord
import genshin
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME, HB_GAME_TO_GPY_GAME, OFFLOAD_APIS
from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.embeds import Embed
    from hoyo_buddy.types import OffloadAPI


API_TOKEN = os.environ["DAILY_CHECKIN_API_TOKEN"]
MAX_API_ERROR_COUNT = 10


class AutoRedeem:
    _total_redeem_count: ClassVar[int]
    _bot: ClassVar[HoyoBuddy]
    _dead_codes: ClassVar[set[str]]
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def execute(cls, bot: HoyoBuddy, game: genshin.Game | None = None, codes: list[str] | None = None) -> None:
        """Redeem codes for accounts that have auto redeem enabled.

        Args:
            bot: The bot instance.
            game: The game to redeem codes for, all games if None.
            codes: The codes to redeem, None to fetch from API.
        """
        async with cls._lock:
            try:
                logger.info(f"Starting auto redeem task for game {game or 'all'} and codes {codes or 'from API'}")

                cls._total_redeem_count = 0
                cls._bot = bot
                cls._dead_codes = set()

                games_to_redeem = (genshin.Game.GENSHIN, genshin.Game.STARRAIL, genshin.Game.ZZZ, genshin.Game.TOT)
                game_codes = (
                    {game: codes}
                    if game is not None and codes is not None
                    else {game_: await cls._get_codes(game_) for game_ in games_to_redeem}
                )
                logger.debug(f"Game codes: {game_codes}")

                if game is None:
                    accounts = await HoyoAccount.filter(auto_redeem=True).all()
                else:
                    accounts = await HoyoAccount.filter(auto_redeem=True, game=GPY_GAME_TO_HB_GAME[game]).all()

                queue: asyncio.Queue[HoyoAccount] = asyncio.Queue()
                for account in accounts:
                    if (
                        account.platform is Platform.MIYOUSHE
                        or HB_GAME_TO_GPY_GAME[account.game] not in game_codes
                        or ("cookie_token" not in account.cookies and "stoken" not in account.cookies)
                    ):
                        continue
                    await queue.put(account)

                tasks = [asyncio.create_task(cls._redeem_code_task(queue, api, game_codes)) for api in OFFLOAD_APIS]
                tasks.append(asyncio.create_task(cls._redeem_code_task(queue, "LOCAL", game_codes)))

                await queue.join()
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                bot.capture_exception(e)
            finally:
                logger.info(f"Auto redeem task completed, total redeem count: {cls._total_redeem_count}")

    @classmethod
    async def _get_codes(cls, game: genshin.Game) -> list[str]:
        async with cls._bot.session.get(f"https://hoyo-codes.seria.moe/codes?game={game.value}") as resp:
            data = await resp.json()
            return [code["code"] for code in data["codes"]]

    @classmethod
    async def _redeem_code_task(
        cls,
        queue: asyncio.Queue[HoyoAccount],
        api_name: OffloadAPI | Literal["LOCAL"],
        game_codes: dict[genshin.Game, list[str]],
    ) -> None:
        logger.info(f"Auto redeem task started for api: {api_name}")

        bot = cls._bot
        if api_name != "LOCAL":
            # test if the api is working
            async with bot.session.get(OFFLOAD_APIS[api_name]) as resp:
                if resp.status != 200:
                    msg = f"API {api_name} returned {resp.status}"
                    raise RuntimeError(msg)

        api_error_count = 0

        while True:
            account = await queue.get()
            codes = game_codes[HB_GAME_TO_GPY_GAME[account.game]]

            try:
                await account.fetch_related("user")
                embed = await cls._redeem_codes(api_name, account, codes)
            except Exception as e:
                await queue.put(account)
                api_error_count += 1

                logger.warning(f"Auto redeem failed for {account}")
                cls._bot.capture_exception(e)
                if api_error_count >= MAX_API_ERROR_COUNT:
                    msg = f"Auto redeem API {api_name} failed for {api_error_count} accounts"
                    raise RuntimeError(msg) from None
            else:
                if embed is not None:
                    cls._total_redeem_count += 1
                    try:
                        await cls._bot.dm_user(account.user.id, embed=embed)
                    except Exception as e:
                        cls._bot.capture_exception(e)
            finally:
                queue.task_done()

    @classmethod
    async def _handle_error(cls, account: HoyoAccount, locale: discord.Locale, e: Exception) -> None:
        embed, recognized = get_error_embed(e, locale)
        if not recognized:
            raise e

        embed.add_acc_info(account, blur=False)

        content = LocaleStr(key="auto_redeem_error.content")
        await cls._bot.dm_user(account.user.id, embed=embed, content=content.translate(locale))

        account.auto_redeem = False
        await account.save(update_fields=("auto_redeem",))

    @classmethod
    async def _redeem_codes(
        cls, api_name: OffloadAPI | Literal["LOCAL"], account: HoyoAccount, codes: list[str]
    ) -> Embed | None:
        codes_: list[str] = []
        for code in codes:
            if code in account.redeemed_codes or code in cls._dead_codes:
                continue
            codes_.append(code)

        if not codes_:
            return None

        await account.user.fetch_related("settings")
        locale = account.user.settings.locale or discord.Locale.american_english
        client = account.client
        client.set_lang(locale)

        if api_name == "LOCAL":
            try:
                embed = await account.client.redeem_codes(codes_, locale=locale, blur=False)
                embed.set_footer(text=LocaleStr(key="auto_redeem_footer"))
            except Exception as e:
                await cls._handle_error(account, locale, e)
                return None
            else:
                account.redeemed_codes.extend(codes)
                # remove duplicates
                account.redeemed_codes = list(set(account.redeemed_codes))
                await account.save(update_fields=("redeemed_codes",))

                return embed

        # API redeem
        assert client.game is not None
        results: list[tuple[str, str, bool]] = []

        for code in codes_:
            payload = {
                "token": API_TOKEN,
                "cookies": account.cookies,
                "game": client.game.value,
                "code": code,
                "uid": account.uid,
            }
            try:
                results.append(await cls._redeem_code(api_name, account, locale, code, payload))
            except Exception as e:
                await cls._handle_error(account, locale, e)
                return None

            await asyncio.sleep(6)

        return client.get_redeem_codes_embed(results, locale=locale, blur=False)

    @classmethod
    async def _redeem_code(
        cls, api_name: OffloadAPI, account: HoyoAccount, locale: discord.Locale, code: str, payload: dict[str, str]
    ) -> tuple[str, str, bool]:
        api_url = OFFLOAD_APIS[api_name]

        logger.debug(f"Redeem payload: {payload}")

        async with cls._bot.session.post(f"{api_url}/redeem/", json=payload) as resp:
            if resp.status == 502:
                await asyncio.sleep(20)
                return await cls._redeem_code(api_name, account, locale, code, payload)

            if resp.status in {200, 400, 500}:
                data = await resp.json()
                logger.debug(f"Redeem response: {data}")

                if (cookies := data.get("cookies")) and account.cookies != cookies:
                    account.cookies = cookies
                    await account.save(update_fields=("cookies",))

                if resp.status == 200:
                    await cls._add_to_redeemed_codes(account, code)
                    return (code, LocaleStr(key="redeem_code.success").translate(locale), True)

                if resp.status == 400:
                    if data["retcode"] == 1001:
                        # Redemption cooldown
                        await asyncio.sleep(20)
                        return await cls._redeem_code(api_name, account, locale, code, payload)

                    e = genshin.GenshinException(data)
                    if e.retcode in {999, 1000}:
                        # Cookie token expired or refresh failed
                        raise e

                    if e.retcode == -2006:
                        # Code reached max redemption limit
                        cls._dead_codes.add(code)

                    embed, recognized = get_error_embed(e, locale)
                    if not recognized:
                        raise e

                    await cls._add_to_redeemed_codes(account, code)
                    assert embed.title is not None

                    if embed.description is None:
                        return (code, embed.title, False)
                    return (code, f"{embed.title}\n{embed.description}", False)

                # 500
                msg = f"API {api_name} errored: {data['message']}"
                raise RuntimeError(msg)

            msg = f"API {api_name} returned {resp.status}"
            raise RuntimeError(msg)

    @classmethod
    async def _add_to_redeemed_codes(cls, account: HoyoAccount, code: str) -> None:
        account.redeemed_codes.append(code)
        account.redeemed_codes = list(set(account.redeemed_codes))
        await account.save(update_fields=("redeemed_codes",))
