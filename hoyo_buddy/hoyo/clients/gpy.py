from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any, Literal, overload

import enka
import genshin
import hakushin
import python_socks

from ... import models
from ...bot.error_handler import get_error_embed
from ...constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    DMG_BONUS_IDS,
    ELEMENT_TO_BONUS_PROP_ID,
    GPY_LANG_TO_LOCALE,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    contains_traveler_id,
    convert_fight_prop,
)
from ...db.models import EnkaCache, HoyoAccount, JSONFile
from ...embeds import DefaultEmbed
from ...enums import Game, GenshinElement
from ...l10n import LocaleStr, Translator
from ...utils import set_or_update_dict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from discord import Locale


class GenshinClient(genshin.Client):
    def __init__(self, account: HoyoAccount) -> None:
        game = HB_GAME_TO_GPY_GAME[account.game]
        region = account.region or genshin.utility.recognize_region(account.uid, game=game) or genshin.Region.OVERSEAS
        env: Literal["dev", "prod", "test"] = os.environ["ENV"]  # pyright: ignore[reportAssignmentType]
        super().__init__(
            account.cookies,
            game=game,
            uid=account.uid,
            region=region,
            device_id=account.device_id,
            device_fp=account.device_fp,
            proxy="socks5://127.0.0.1:9091" if env == "prod" and region is genshin.Region.OVERSEAS else None,
            debug=env == "dev",
            cache=genshin.SQLiteCache(static_ttl=3600 * 24 * 31),
        )
        self._account = account

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return await super().request(*args, **kwargs)
        except (python_socks.ProxyError, python_socks.ProxyTimeoutError):
            self.proxy = None
            return await super().request(*args, **kwargs)
        except ConnectionResetError:
            await asyncio.sleep(1.0)
            return await super().request(*args, **kwargs)

    def set_lang(self, locale: Locale) -> None:
        self.lang = "zh-cn" if self.region is genshin.Region.CHINESE else LOCALE_TO_GPY_LANG.get(locale, "en-us")

    def get_daily_reward_embed(
        self, daily_reward: genshin.models.DailyReward, locale: Locale, translator: Translator, *, blur: bool
    ) -> DefaultEmbed:
        return (
            DefaultEmbed(
                locale,
                translator,
                title=LocaleStr(key="reward_claimed_title"),
                description=f"{daily_reward.name} x{daily_reward.amount}",
            )
            .set_thumbnail(url=daily_reward.icon)
            .add_acc_info(self._account, blur=blur)
        )

    @staticmethod
    def _convert_character_id_to_enka_format(character_id: str) -> str:
        """Convert character ID to the format used by EnkaAPI."""
        return (
            AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID[character_id] if contains_traveler_id(character_id) else character_id
        )

    async def update_pc_icons(self) -> None:
        fields = await self.get_lineup_fields(use_cache=False)
        pc_icons = {str(character.id): character.pc_icon for character in fields.characters}
        await JSONFile.write("pc_icons.json", pc_icons)

    @staticmethod
    async def convert_gi_character(character: genshin.models.GenshinDetailCharacter) -> models.HoyolabGICharacter:
        """Convert GenshinDetailCharacter from gpy to HoyolabGICharacter that's used for drawing cards."""
        weapon = models.HoyolabGIWeapon(
            name=character.weapon.name,
            icon=character.weapon.icon,
            refinement=character.weapon.refinement,
            level=character.weapon.level,
            max_level=hakushin.utils.get_max_level_from_ascension(character.weapon.ascension, hakushin.Game.GI),
            rarity=character.weapon.rarity,
            stats=[
                models.HoyolabGIStat(
                    type=convert_fight_prop(character.weapon.main_stat.info.type),
                    formatted_value=character.weapon.main_stat.final,
                )
            ],
        )
        if character.weapon.sub_stat is not None:
            weapon.stats.append(
                models.HoyolabGIStat(
                    type=convert_fight_prop(character.weapon.sub_stat.info.type),
                    formatted_value=character.weapon.sub_stat.final,
                )
            )

        constellations = [
            models.HoyolabGIConst(icon=const.icon, unlocked=const.activated) for const in character.constellations
        ]

        artifacts = [
            models.HoyolabGIArtifact(
                icon=artifact.icon,
                rarity=artifact.rarity,
                level=artifact.level,
                main_stat=models.HoyolabGIStat(
                    type=convert_fight_prop(artifact.main_stat.info.type), formatted_value=artifact.main_stat.value
                ),
                sub_stats=[
                    models.HoyolabGIStat(type=convert_fight_prop(sub_stat.info.type), formatted_value=sub_stat.value)
                    for sub_stat in artifact.sub_stats
                ],
                pos=artifact.pos,
            )
            for artifact in character.artifacts
        ]

        highest_dmg_bonus_stat = None
        for prop in character.selected_properties:
            if prop.info.type in DMG_BONUS_IDS:
                highest_dmg_bonus_stat = models.HoyolabGIStat(
                    type=convert_fight_prop(prop.info.type), formatted_value=prop.final
                )
            break
        if highest_dmg_bonus_stat is None:
            prop_id = ELEMENT_TO_BONUS_PROP_ID[GenshinElement(character.element)]
            prop = next((prop for prop in character.element_properties if prop.info.type == prop_id), None)
            if prop is None:
                msg = f"Couldn't find the highest damage bonus stat for {character.name} ({character.element})"
                raise ValueError(msg)

            highest_dmg_bonus_stat = models.HoyolabGIStat(type=convert_fight_prop(prop_id), formatted_value=prop.final)

        async with enka.GenshinClient() as client:
            talent_order = client._assets.character_data[str(character.id)]["SkillOrder"]

        return models.HoyolabGICharacter(
            id=character.id,
            name=character.name,
            element=GenshinElement(character.element),
            highest_dmg_bonus_stat=highest_dmg_bonus_stat,
            stats={
                convert_fight_prop(prop.info.type): models.HoyolabGIStat(
                    type=convert_fight_prop(prop.info.type), formatted_value=prop.final
                )
                for prop in character.selected_properties
            },
            rarity=character.rarity,
            weapon=weapon,
            constellations=constellations,
            talent_order=talent_order,
            talents=[
                models.HoyolabGITalent(icon=talent.icon, level=talent.level, id=talent.id)
                for talent in character.skills
            ],
            artifacts=artifacts,
            friendship_level=character.friendship,
            level=character.level,
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(character.level, True, hakushin.Game.GI), hakushin.Game.GI
            ),
            icon=models.HoyolabGICharacterIcon(gacha=character.gacha_art),
        )

    @staticmethod
    def convert_hsr_character(
        character: genshin.models.StarRailDetailCharacter, property_info: dict[str, genshin.models.PropertyInfo]
    ) -> models.HoyolabHSRCharacter:
        """Convert StarRailDetailCharacter from gpy to HoyolabHSRCharacter that's used for drawing cards."""
        prop_icons: dict[int, str] = {prop.property_type: prop.icon for prop in property_info.values()}

        light_cone = (
            models.LightCone(
                id=character.equip.id,
                level=character.equip.level,
                superimpose=character.equip.rank,
                name=character.equip.name,
                max_level=hakushin.utils.get_max_level_from_ascension(
                    hakushin.utils.get_ascension_from_level(character.equip.level, True, hakushin.Game.HSR),
                    hakushin.Game.HSR,
                ),
            )
            if character.equip is not None
            else None
        )
        relics = [
            models.Relic(
                id=relic.id,
                level=relic.level,
                rarity=relic.rarity,
                icon=relic.icon,
                main_stat=models.Stat(
                    type=relic.main_property.property_type,
                    icon=prop_icons[relic.main_property.property_type],
                    formatted_value=relic.main_property.value,
                ),
                sub_stats=[
                    models.Stat(
                        type=sub_property.property_type,
                        icon=prop_icons[sub_property.property_type],
                        formatted_value=sub_property.value,
                    )
                    for sub_property in relic.properties
                ],
                type=enka.hsr.RelicType(relic.pos),
            )
            for relic in list(character.relics) + list(character.ornaments)
        ]
        return models.HoyolabHSRCharacter(
            id=str(character.id),
            element=character.element,
            name=character.name,
            level=character.level,
            eidolons_unlocked=character.rank,
            light_cone=light_cone,
            relics=relics,
            stats=[
                models.Stat(icon=prop_icons[prop.property_type], formatted_value=prop.final, type=prop.property_type)
                for prop in character.properties
            ],
            traces=[
                models.Trace(anchor=skill.anchor, icon=skill.item_url, level=skill.level) for skill in character.skills
            ],
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(character.level, True, hakushin.Game.HSR), hakushin.Game.HSR
            ),
        )

    def _update_live_status(
        self, data: dict[str, Any], extras: dict[str, dict[str, Any]], *, live: bool, game: Game
    ) -> None:
        cache_data: dict[str, Any] = {"live": live, "locale": GPY_LANG_TO_LOCALE[self.lang].value}
        if game is Game.ZZZ:
            parsed = genshin.models.ZZZFullAgent(**data)
            key = f"{parsed.id}-hoyolab"
            set_or_update_dict(extras, key, cache_data)
        elif game is Game.STARRAIL:
            parsed = genshin.models.StarRailDetailCharacters(**data)
            for character in parsed.avatar_list:
                key = f"{character.id}-hoyolab"
                set_or_update_dict(extras, key, cache_data)
        elif game is Game.GENSHIN:
            parsed = genshin.models.GenshinDetailCharacters(**data)
            for character in parsed.characters:
                key = f"{character.id}-hoyolab"
                set_or_update_dict(extras, key, cache_data)

    async def get_hoyolab_gi_characters(self) -> list[models.HoyolabGICharacter]:
        """Get Genshin Impact detailed characters in HoyolabGI format."""
        cache, _ = await EnkaCache.get_or_create(uid=self.uid)

        try:
            live_data = dict(await self.get_genshin_detailed_characters(self._account.uid, return_raw_data=True))
        except genshin.GenshinException as e:
            if not cache.hoyolab or e.retcode != 1005:
                raise

            self._update_live_status(cache.hoyolab, cache.extras, live=False, game=Game.GENSHIN)
            await cache.save(update_fields=("extras"))
        else:
            cache.hoyolab = live_data
            self._update_live_status(live_data, cache.extras, live=True, game=Game.GENSHIN)
            await cache.save(update_fields=("hoyolab", "extras"))

        parsed = genshin.models.GenshinDetailCharacters(**cache.hoyolab)
        return [await self.convert_gi_character(chara) for chara in parsed.characters]

    async def get_hoyolab_hsr_characters(self) -> list[models.HoyolabHSRCharacter]:
        """Get characters in HoyolabHSR format."""
        cache, _ = await EnkaCache.get_or_create(uid=self.uid)

        try:
            live_data = (await self.get_starrail_characters(self.uid)).model_dump(by_alias=True)
        except genshin.GenshinException as e:
            if not cache.hoyolab or e.retcode != 1005:
                raise

            self._update_live_status(cache.hoyolab, cache.extras, live=False, game=Game.STARRAIL)
            await cache.save(update_fields=("extras"))
        else:
            cache.hoyolab = live_data
            self._update_live_status(live_data, cache.extras, live=True, game=Game.STARRAIL)
            await cache.save(update_fields=("hoyolab", "extras"))

        parsed = genshin.models.StarRailDetailCharacters(**cache.hoyolab)
        return [self.convert_hsr_character(chara, dict(parsed.property_info)) for chara in parsed.avatar_list]

    @overload
    async def get_zzz_agent_info(self, character_id: Sequence[int]) -> Sequence[genshin.models.ZZZFullAgent]: ...
    @overload
    async def get_zzz_agent_info(self, character_id: int) -> genshin.models.ZZZFullAgent: ...
    async def get_zzz_agent_info(
        self, character_id: Sequence[int] | int
    ) -> Sequence[genshin.models.ZZZFullAgent] | genshin.models.ZZZFullAgent:
        if isinstance(character_id, int):
            # Only do cache stuff when there is a single character
            cache, _ = await EnkaCache.get_or_create(uid=self.uid)

            try:
                live_data = (await super().get_zzz_agent_info(character_id)).model_dump(by_alias=True)
            except genshin.GenshinException as e:
                if not cache.hoyolab_zzz or e.retcode != 1005:
                    raise

                self._update_live_status(cache.hoyolab_zzz, cache.extras, live=False, game=Game.ZZZ)
                await cache.save(update_fields=("extras"))
            else:
                cache.hoyolab_zzz = cache.hoyolab_zzz or {}
                cache.hoyolab_zzz.update({str(character_id): live_data})
                self._update_live_status(live_data, cache.extras, live=False, game=Game.ZZZ)
                await cache.save(update_fields=("hoyolab_zzz", "extras"))

            return genshin.models.ZZZFullAgent(**cache.hoyolab_zzz[str(character_id)])
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
        self, codes: Sequence[str], *, locale: Locale, translator: Translator, inline: bool, blur: bool = True
    ) -> DefaultEmbed:
        """Redeem multiple codes and return an embed with the results."""
        results: list[tuple[str, str, bool]] = []

        for code in codes:
            if not code:
                continue

            msg, success = await self.redeem_code(code.strip(), locale=locale, translator=translator)
            results.append((code, msg, success))

            await asyncio.sleep(6)

        return self.get_redeem_codes_embed(results, locale=locale, translator=translator, inline=inline, blur=blur)

    def get_redeem_codes_embed(
        self, results: list[tuple[str, str, bool]], *, locale: Locale, translator: Translator, inline: bool, blur: bool
    ) -> DefaultEmbed:
        # get the first 25 results
        results = results[:25]
        embed = DefaultEmbed(locale, translator, title=LocaleStr(key="redeem_command_embed.title")).add_acc_info(
            self._account, blur=blur
        )
        for result in results:
            name = f"{'✅' if result[2] else '❌'} {result[0]}"
            embed.add_field(name=name, value=result[1], inline=inline)

        return embed

    async def redeem_code(self, code: str, *, locale: Locale, translator: Translator) -> tuple[str, bool]:
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
            await asyncio.sleep(20)
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
            return None

        cookies = genshin.parse_cookie(self._account.cookies)
        if "stoken" not in cookies or "mid" not in cookies:
            return None

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
            endpoint, game=game, method=method, lang=lang, params=params, headers=headers, challenge=challenge, **kwargs
        )
