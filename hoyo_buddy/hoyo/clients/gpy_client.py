import asyncio
import pickle
from random import uniform
from typing import TYPE_CHECKING

import genshin
from seria.utils import read_json, write_json

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr, Translator
from ...constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    GPY_LANG_TO_LOCALE,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    TRAVELER_IDS,
    contains_traveler_id,
)
from ...db.models import EnkaCache, HoyoAccount
from ...embeds import DefaultEmbed
from ...enums import TalentBoost
from ...models import HoyolabHSRCharacter, LightCone, Relic, Stat, Trace
from ...utils import get_now
from .ambr_client import AmbrAPIClient
from .base import BaseClient
from .enka_client import EnkaAPI

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale


TALENT_BOOST_DATA_PATH = "./.static/talent_boost.json"
PC_ICON_DATA_PATH = "./.static/pc_icons.json"
GI_TALENT_LEVEL_DATA_PATH = "./.static/talent_levels/gi_{uid}.json"


class GenshinClient(genshin.Client, BaseClient):
    def __init__(
        self,
        account: HoyoAccount,
    ) -> None:
        game = HB_GAME_TO_GPY_GAME[account.game]
        region = genshin.utility.recognize_region(account.uid, game=game) or genshin.Region.OVERSEAS
        super().__init__(account.cookies, game=game, uid=account.uid, region=region)
        self._account = account

    def set_lang(self, locale: "Locale") -> None:
        if self.region is genshin.Region.CHINESE:
            self.lang = "zh-cn"
        else:
            self.lang = LOCALE_TO_GPY_LANG.get(locale, "en-us")

    def get_daily_reward_embed(
        self,
        daily_reward: genshin.models.DailyReward,
        locale: "Locale",
        translator: Translator,
    ) -> DefaultEmbed:
        embed = (
            DefaultEmbed(
                locale,
                translator,
                title=LocaleStr("Daily Check-In Reward Claimed", key="reward_claimed_title"),
                description=f"{daily_reward.name} x{daily_reward.amount}",
            )
            .set_thumbnail(url=daily_reward.icon)
            .add_acc_info(self._account)
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
        await write_json(PC_ICON_DATA_PATH, pc_icons)

    async def update_gi_chara_talent_levels(
        self, characters: "Sequence[genshin.models.Character]"
    ) -> None:
        """Update multiple genshin impact character talent levels."""
        for i, character in enumerate(characters):
            await self.update_gi_chara_talent_level(character)
            await asyncio.sleep(3.0 if i % 15 == 0 else uniform(0.5, 0.8))

    async def update_gi_chara_talent_level(self, character: genshin.models.Character) -> None:
        """Update genshin impact character talent level."""
        talent_level_data: dict[str, str] = await read_json(
            GI_TALENT_LEVEL_DATA_PATH.format(uid=self.uid)
        )
        talent_boost_data: dict[str, int] = await read_json(TALENT_BOOST_DATA_PATH)

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
            await write_json(TALENT_BOOST_DATA_PATH, talent_boost_data)
        else:
            talent_boost = TalentBoost(talent_boost_data[character_id])

        # Get talent order
        async with EnkaAPI() as client:
            talent_order = client.get_character_talent_order(
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

        filename = GI_TALENT_LEVEL_DATA_PATH.format(uid=self.uid)
        await write_json(filename, talent_level_data)

    def convert_hsr_character(
        self,
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
                main_affix=Stat(
                    type=relic.main_property.property_type,
                    icon=prop_icons[relic.main_property.property_type],
                    displayed_value=relic.main_property.value,
                ),
                sub_affixes=[
                    Stat(
                        type=sub_property.property_type,
                        icon=prop_icons[sub_property.property_type],
                        displayed_value=sub_property.value,
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
            eidolon=character.rank,
            light_cone=light_cone,
            relics=relics,
            stats=[
                Stat(
                    icon=prop_icons[prop.property_type],
                    displayed_value=prop.final,
                    type=prop.property_type,
                )
                for prop in character.properties
            ],
            trace_tree=[
                Trace(anchor=skill.anchor, icon=skill.item_url, level=skill.level)
                for skill in character.skills
            ],
        )
        return hsr_chara

    async def get_hoyolab_hsr_characters(self) -> list[HoyolabHSRCharacter]:
        """Get characters in HoyolabHSR format."""
        cache, _ = await EnkaCache.get_or_create(uid=self.uid)

        try:
            data = await self.get_starrail_characters(self.uid)
            live_data = [
                self.convert_hsr_character(character, dict(data.property_info))
                for character in data.avatar_list
            ]
        except genshin.GenshinException as e:
            if cache.hoyolab is None or e.retcode != 1005:
                raise

            cache.extras = self._set_all_live_to_false(cache.hoyolab, cache.extras)
            await cache.save(update_fields=("extras",))
            cache_data: list[HoyolabHSRCharacter] = pickle.loads(cache.hoyolab)
        else:
            cache.hoyolab, cache.extras = self._update_cache_with_live_data(
                cache.hoyolab, cache.extras, live_data, GPY_LANG_TO_LOCALE[self.lang]
            )
            await cache.save(update_fields=("hoyolab", "extras"))
            cache_data: list[HoyolabHSRCharacter] = pickle.loads(cache.hoyolab)

        return cache_data

    async def update_cookie_token(self) -> None:
        """Update the cookie token."""
        parsed_cookies = genshin.parse_cookie(self._account.cookies)
        cookies = await genshin.fetch_cookie_with_stoken_v2(parsed_cookies, token_types=[2, 4])
        parsed_cookies.update(cookies)
        self.set_cookies(parsed_cookies)
        new_str_cookies = "; ".join(f"{k}={v}" for k, v in parsed_cookies.items())

        # Update cookie in the db via raw sql to avoid circular import
        self._account.cookies = new_str_cookies
        await self._account.save(update_fields=("cookies",))

    async def redeem_codes(
        self,
        codes: "Sequence[str]",
        *,
        locale: "Locale",
        translator: Translator,
        inline: bool,
        blur: bool = True,
    ) -> DefaultEmbed:
        """Redeem multiple gift codes and return an embed with the results."""
        results: list[tuple[str, str, bool]] = []

        for code in codes:
            if not code:
                continue

            msg, success = await self.redeem_code(
                code.strip(), locale=locale, translator=translator
            )
            results.append((code, msg, success))

            if len(code) > 1:
                # only sleep if there are more than 1 code
                await asyncio.sleep(uniform(5.5, 6.5))

        # get the first 25 results
        results = results[:25]
        embed = DefaultEmbed(
            locale,
            translator,
            title=LocaleStr("Gift Code Redemption Results", key="redeem_command_embed.title"),
        ).add_acc_info(self._account, blur=blur)
        for result in results:
            name = f"{'✅' if result[2] else '❌'} {result[0]}"
            embed.add_field(name=name, value=result[1], inline=inline)

        return embed

    async def redeem_code(
        self, code: str, *, locale: "Locale", translator: Translator
    ) -> tuple[str, bool]:
        """Redeem a gift code, return a message and a boolean indicating success."""
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
            msg = LocaleStr("Gift code claimed", key="redeem_code.success").translate(
                translator, locale
            )

        return msg, success
