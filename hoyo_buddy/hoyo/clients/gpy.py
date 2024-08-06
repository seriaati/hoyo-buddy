from __future__ import annotations

import asyncio
import os
from operator import attrgetter
from random import uniform
from typing import TYPE_CHECKING, Any, overload

import genshin
import hakushin
import python_socks

from ...bot.error_handler import get_error_embed
from ...constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    GPY_LANG_TO_LOCALE,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    TRAVELER_IDS,
    contains_traveler_id,
)
from ...db.models import EnkaCache, HoyoAccount, JSONFile
from ...embeds import DefaultEmbed
from ...enums import TalentBoost
from ...l10n import LocaleStr, Translator
from ...models import HoyolabHSRCharacter, LightCone, Relic, Stat, Trace
from ...utils import get_now
from .ambr import AmbrAPIClient
from .enka.gi import EnkaGIClient

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from discord import Locale


class GenshinClient(genshin.Client):
    def __init__(
        self,
        account: HoyoAccount,
    ) -> None:
        game = HB_GAME_TO_GPY_GAME[account.game]
        region = (
            account.region
            or genshin.utility.recognize_region(account.uid, game=game)
            or genshin.Region.OVERSEAS
        )
        super().__init__(
            account.cookies,
            game=game,
            uid=account.uid,
            region=region,
            device_id=account.device_id,
            device_fp=account.device_fp,
            proxy="socks5://127.0.0.1:9091"
            if os.environ["ENV"] == "prod" and region is genshin.Region.OVERSEAS
            else None,
            debug=True,
        )
        self._account = account

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await super().request(*args, **kwargs)
        except python_socks.ProxyError:
            self.proxy = None
            return await super().request(*args, **kwargs)

    def set_lang(self, locale: Locale) -> None:
        if self.region is genshin.Region.CHINESE:
            self.lang = "zh-cn"
        else:
            self.lang = LOCALE_TO_GPY_LANG.get(locale, "en-us")

    def get_daily_reward_embed(
        self,
        daily_reward: genshin.models.DailyReward,
        locale: Locale,
        translator: Translator,
        *,
        blur: bool,
    ) -> DefaultEmbed:
        embed = (
            DefaultEmbed(
                locale,
                translator,
                title=LocaleStr(key="reward_claimed_title"),
                description=f"{daily_reward.name} x{daily_reward.amount}",
            )
            .set_thumbnail(url=daily_reward.icon)
            .add_acc_info(self._account, blur=blur)
        )
        return embed

    @staticmethod
    def convert_chara_id_to_ambr_format(character: genshin.models.Character) -> str:
        """Convert character ID to the format used by AmbrAPI (traveler ID contains element)."""
        return (
            f"{character.id}-{character.element.lower()}"
            if character.id in TRAVELER_IDS
            else str(character.id)
        )

    @staticmethod
    def _convert_character_id_to_enka_format(character_id: str) -> str:
        """Convert character ID to the format used by EnkaAPI."""
        return (
            AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID[character_id]
            if contains_traveler_id(character_id)
            else character_id
        )

    async def update_pc_icons(self) -> None:
        fields = await self.get_lineup_fields()
        pc_icons = {str(character.id): character.pc_icon for character in fields.characters}
        await JSONFile.write("pc_icons.json", pc_icons)

    async def update_gi_chara_talent_levels(
        self, characters: Sequence[genshin.models.Character]
    ) -> None:
        """Update multiple GI character talent levels.

        Args:
            characters: The characters to update.
        """
        # Sort characters by level in descending order
        characters = sorted(characters, key=attrgetter("level"), reverse=True)

        for i, character in enumerate(characters):
            try:
                await self.update_gi_chara_talent_level(character)
            except genshin.GenshinException:
                await asyncio.sleep(15.0)
            else:
                await asyncio.sleep(3.0 if i % 15 == 0 else uniform(0.5, 0.8))

    async def update_gi_chara_talent_level(self, character: genshin.models.Character) -> None:
        """Update GI character talent level."""
        talent_level_data: dict[str, str] = await JSONFile.read(f"talent_levels/gi_{self.uid}.json")
        talent_boost_data: dict[str, int] = await JSONFile.read("talent_boost.json")

        try:
            details = await self.get_character_details(character.id)
        except genshin.GenshinException as e:
            if e.retcode == -502002:  # Calculator sync not enabled
                await self._enable_calculator_sync()
                await asyncio.sleep(uniform(0.5, 0.8))
                details = await self.get_character_details(character.id)
            else:
                raise

        character_id = self.convert_chara_id_to_ambr_format(character)

        # Get talent boost type
        if character_id not in talent_boost_data:
            async with AmbrAPIClient() as client:
                talent_boost = await client.fetch_talent_boost(character_id)
            talent_boost_data[character_id] = talent_boost.value
            await JSONFile.write("talent_boost.json", talent_boost_data)
        else:
            talent_boost = TalentBoost(talent_boost_data[character_id])

        # Get talent order
        client = EnkaGIClient()
        talent_order = await client.get_character_talent_order(
            self._convert_character_id_to_enka_format(character_id)
        )

        # Get talent levels
        talent_levels: list[int] = []
        for i, talent_id in enumerate(talent_order):
            talent = next(talent for talent in details.talents if talent.id == talent_id)

            c3 = character.constellations[2]

            if (  # noqa: PLR0916
                i == 1 and talent_boost is TalentBoost.BOOST_E and c3.activated
            ) or (i == 2 and talent_boost is TalentBoost.BOOST_Q and c3.activated):
                talent_levels.append(talent.level + 3)
            else:
                talent_levels.append(talent.level)

        talent_str = "/".join(str(level) for level in talent_levels)
        talent_level_data[character_id] = talent_str

        talent_level_data["updated_at"] = get_now().isoformat()

        await JSONFile.write(f"talent_levels/gi_{self.uid}.json", talent_level_data)

    @staticmethod
    def convert_hsr_character(
        character: genshin.models.StarRailDetailCharacter,
        property_info: dict[str, genshin.models.PropertyInfo],
    ) -> HoyolabHSRCharacter:
        """Convert StarRailDetailCharacter from gpy to HoyolabHSRCharacter that's used for drawing cards."""
        prop_icons: dict[int, str] = {
            prop.property_type: prop.icon for prop in property_info.values()
        }

        light_cone = (
            LightCone(
                id=character.equip.id,
                level=character.equip.level,
                superimpose=character.equip.rank,
                name=character.equip.name,
                max_level=hakushin.utils.get_max_level_from_ascension(
                    hakushin.utils.get_ascension_from_level(
                        character.equip.level, True, hakushin.Game.HSR
                    ),
                    hakushin.Game.HSR,
                ),
            )
            if character.equip is not None
            else None
        )
        relics = [
            Relic(
                id=relic.id,
                level=relic.level,
                rarity=relic.rarity,
                icon=relic.icon,
                main_stat=Stat(
                    type=relic.main_property.property_type,
                    icon=prop_icons[relic.main_property.property_type],
                    formatted_value=relic.main_property.value,
                ),
                sub_stats=[
                    Stat(
                        type=sub_property.property_type,
                        icon=prop_icons[sub_property.property_type],
                        formatted_value=sub_property.value,
                    )
                    for sub_property in relic.properties
                ],
            )
            for relic in list(character.relics) + list(character.ornaments)
        ]
        hsr_chara = HoyolabHSRCharacter(
            id=str(character.id),
            element=character.element,
            name=character.name,
            level=character.level,
            eidolons_unlocked=character.rank,
            light_cone=light_cone,
            relics=relics,
            stats=[
                Stat(
                    icon=prop_icons[prop.property_type],
                    formatted_value=prop.final,
                    type=prop.property_type,
                )
                for prop in character.properties
            ],
            traces=[
                Trace(anchor=skill.anchor, icon=skill.item_url, level=skill.level)
                for skill in character.skills
            ],
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(character.level, True, hakushin.Game.HSR),
                hakushin.Game.HSR,
            ),
        )
        return hsr_chara

    def _update_live_status(
        self,
        data: dict[str, Any],
        extras: dict[str, dict[str, Any]],
        live: bool,
        *,
        zzz: bool,
    ) -> None:
        cache_data = {
            "live": live,
            "locale": GPY_LANG_TO_LOCALE[self.lang].value,
        }
        if zzz:
            parsed = genshin.models.ZZZFullAgent(**data)
            key = f"{parsed.id}-hoyolab"
            if key not in extras:
                extras[key] = cache_data
            else:
                extras[key].update(cache_data)
        else:
            parsed = genshin.models.StarRailDetailCharacters(**data)
            for character in parsed.avatar_list:
                key = f"{character.id}-hoyolab"
                if key not in extras:
                    extras[key] = cache_data
                else:
                    extras[key].update(cache_data)

    async def get_hoyolab_hsr_characters(self) -> list[HoyolabHSRCharacter]:
        """Get characters in HoyolabHSR format."""
        cache, _ = await EnkaCache.get_or_create(uid=self.uid)

        try:
            live_data = (await self.get_starrail_characters(self.uid)).dict()
        except genshin.GenshinException as e:
            if not cache.hoyolab or e.retcode != 1005:
                raise

            self._update_live_status(cache.hoyolab, cache.extras, False, zzz=False)
            await cache.save(update_fields=("extras"))
        else:
            cache.hoyolab = live_data
            self._update_live_status(live_data, cache.extras, True, zzz=False)
            await cache.save(update_fields=("hoyolab", "extras"))

        parsed = genshin.models.StarRailDetailCharacters(**cache.hoyolab)
        return [
            self.convert_hsr_character(chara, dict(parsed.property_info))
            for chara in parsed.avatar_list
        ]

    @overload
    async def get_zzz_agent_info(
        self, character_id: Sequence[int]
    ) -> Sequence[genshin.models.ZZZFullAgent]: ...
    @overload
    async def get_zzz_agent_info(self, character_id: int) -> genshin.models.ZZZFullAgent: ...
    async def get_zzz_agent_info(
        self, character_id: Sequence[int] | int
    ) -> Sequence[genshin.models.ZZZFullAgent] | genshin.models.ZZZFullAgent:
        if isinstance(character_id, int):
            # Only do cache stuff when there is a single character
            cache, _ = await EnkaCache.get_or_create(uid=self.uid)

            try:
                live_data = (await super().get_zzz_agent_info(character_id)).dict()
            except genshin.GenshinException as e:
                if not cache.hoyolab_zzz or e.retcode != 1005:
                    raise

                self._update_live_status(cache.hoyolab_zzz, cache.extras, False, zzz=True)
                await cache.save(update_fields=("extras"))
            else:
                cache.hoyolab_zzz = cache.hoyolab_zzz or {}
                cache.hoyolab_zzz.update({str(character_id): live_data})
                self._update_live_status(live_data, cache.extras, True, zzz=True)
                await cache.save(update_fields=("hoyolab_zzz", "extras"))

            parsed = genshin.models.ZZZFullAgent(**cache.hoyolab_zzz[str(character_id)])
            return parsed
        return await super().get_zzz_agent_info(character_id)

    async def update_cookie_token(self) -> None:
        """Update the cookie token."""
        parsed_cookies = genshin.parse_cookie(self._account.cookies)
        cookies = await genshin.fetch_cookie_with_stoken_v2(parsed_cookies, token_types=[2, 4])
        parsed_cookies.update(cookies)
        self.set_cookies(parsed_cookies)
        new_str_cookies = "; ".join(f"{k}={v}" for k, v in parsed_cookies.items())

        self._account.cookies = new_str_cookies
        await self._account.save(update_fields=("cookies",))

    async def redeem_codes(
        self,
        codes: Sequence[str],
        *,
        locale: Locale,
        translator: Translator,
        inline: bool,
        blur: bool = True,
    ) -> DefaultEmbed:
        """Redeem multiple codes and return an embed with the results."""
        results: list[tuple[str, str, bool]] = []

        for code in codes:
            if not code:
                continue

            msg, success = await self.redeem_code(
                code.strip(), locale=locale, translator=translator
            )
            results.append((code, msg, success))

            if len(codes) > 1:
                # only sleep if there are more than 1 code
                await asyncio.sleep(uniform(5.5, 6.5))

        # get the first 25 results
        results = results[:25]
        embed = DefaultEmbed(
            locale,
            translator,
            title=LocaleStr(key="redeem_command_embed.title"),
        ).add_acc_info(self._account, blur=blur)
        for result in results:
            name = f"{'✅' if result[2] else '❌'} {result[0]}"
            embed.add_field(name=name, value=result[1], inline=inline)

        return embed

    async def redeem_code(
        self, code: str, *, locale: Locale, translator: Translator
    ) -> tuple[str, bool]:
        """Redeem a code, return a message and a boolean indicating success."""
        success = False
        try:
            await super().redeem_code(code)
        except genshin.InvalidCookies as e:
            # cookie token is invalid
            if all(key in self._account.cookies for key in ("stoken", "ltmid")):
                # cookie token can be refreshed
                try:
                    await self.update_cookie_token()
                except genshin.InvalidCookies as e:
                    # cookie token refresh failed
                    raise genshin.GenshinException({"retcode": 1000}) from e
                else:
                    # cookie token refresh succeeded, redeem code again
                    return await self.redeem_code(code, locale=locale, translator=translator)
            else:
                # cookie token can't be refreshed
                raise genshin.GenshinException({"retcode": 999}) from e
        except genshin.RedemptionCooldown:
            # sleep then retry
            await asyncio.sleep(60.0)
            return await self.redeem_code(code, locale=locale, translator=translator)
        except Exception as e:
            embed, recognized = get_error_embed(e, locale, translator)
            if not recognized:
                raise
            assert embed.title is not None
            if embed.description is None:
                return embed.title, success
            return f"{embed.title}\n{embed.description}", success
        else:
            success = True
            msg = LocaleStr(key="redeem_code.success").translate(translator, locale)

        return msg, success

    async def update_cookies_for_checkin(self) -> dict[str, str] | None:
        """Update client cookies for check-in if the client region is CN."""
        if self.region is genshin.Region.OVERSEAS:
            return

        cookies = genshin.parse_cookie(self._account.cookies)
        cookie_token = (await genshin.cn_fetch_cookie_token_with_stoken_v2(cookies))["cookie_token"]
        cookies["cookie_token"] = cookie_token
        cookies["account_id"] = cookies["ltuid"]
        self.set_cookies(cookies)
        return cookies

    async def request_daily_reward(
        self,
        endpoint: str,
        *,
        game: genshin.Game | None = None,
        method: str = "GET",
        lang: str | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        challenge: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> Mapping[str, str]:
        """Claim the daily reward."""
        await self.update_cookies_for_checkin()
        return await super().request_daily_reward(
            endpoint,
            game=game,
            method=method,
            lang=lang,
            params=params,
            headers=headers,
            challenge=challenge,
            **kwargs,
        )
