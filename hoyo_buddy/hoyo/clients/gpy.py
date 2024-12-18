from __future__ import annotations

import asyncio
import itertools
import os
import random
from typing import TYPE_CHECKING, Any, Literal, overload

import aiohttp
import enka
import genshin
import hakushin
import orjson
from discord import Locale
from dotenv import load_dotenv
from loguru import logger

from hoyo_buddy.exceptions import ProxyAPIError
from hoyo_buddy.web_app.utils import decrypt_string

from ... import models
from ...bot.error_handler import get_error_embed
from ...constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    DMG_BONUS_IDS,
    ELEMENT_TO_BONUS_PROP_ID,
    GPY_LANG_TO_LOCALE,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    POST_REPLIES,
    PROXY_APIS,
    contains_traveler_id,
    convert_fight_prop,
)
from ...db.models import EnkaCache, HoyoAccount, JSONFile
from ...embeds import DefaultEmbed
from ...enums import Game, GenshinElement
from ...l10n import LocaleStr
from ...utils import set_or_update_dict

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


load_dotenv()
env = os.environ["ENV"]

MAX_RETRIES = len(PROXY_APIS)
PROXY_APIS_ = (*PROXY_APIS.values(), "LOCAL")
proxy_api_rotator = itertools.cycle(PROXY_APIS_)


class ProxyGenshinClient(genshin.Client):
    def __init__(
        self, *args: Any, region: genshin.Region = genshin.Region.OVERSEAS, **kwargs: Any
    ) -> None:
        super().__init__(
            *args,
            debug=env == "dev",
            cache=genshin.SQLiteCache(static_ttl=3600 * 24 * 31),
            region=region,
            **kwargs,
        )

    async def request(self, *args: Any, **kwargs: Any) -> Any:
        attempt = 0
        err: Exception | None = None

        while attempt < MAX_RETRIES:
            try:
                return await super().request(*args, **kwargs)
            except (TimeoutError, aiohttp.ClientError) as e:
                err = e

            attempt += 1
            backoff_factor = 2
            jitter = random.uniform(0, 1)
            await asyncio.sleep((backoff_factor**attempt) + jitter)

        if err is None:
            msg = f"HoYo API request failed after {MAX_RETRIES} attempts"
            raise RuntimeError(msg)
        raise err

    async def request_proxy_api(
        self, api_url: str, endpoint: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        payload["token"] = os.environ["DAILY_CHECKIN_API_TOKEN"]
        payload["lang"] = self.lang
        payload["region"] = self.region.value
        if self.game is not None:
            payload["game"] = self.game.value

        no_sensitive_info_payload = {
            k: v for k, v in payload.items() if k not in {"cookies", "token"}
        }
        logger.debug(f"Requesting {api_url}/{endpoint}/ with payload: {no_sensitive_info_payload}")

        attempt = 0
        err: Exception | None = None

        while attempt < MAX_RETRIES:
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(f"{api_url}/{endpoint}/", json=payload) as resp,
                ):
                    if resp.status in {200, 400, 500}:
                        data = await resp.json()
                        if resp.status == 200:
                            return data
                        if resp.status == 400:
                            raise genshin.GenshinException(data)
                        raise Exception(data["message"])

                    err = ProxyAPIError(api_url, resp.status)
            except (TimeoutError, aiohttp.ClientError) as e:
                err = e

            attempt += 1
            backoff_factor = 2
            jitter = random.uniform(0, 1)

            for proxy_api in PROXY_APIS.values():
                if proxy_api != api_url:
                    api_url = proxy_api
            await asyncio.sleep((backoff_factor**attempt) + jitter)

        if err is None:
            msg = f"Proxy API request failed after {MAX_RETRIES} attempts"
            raise RuntimeError(msg)
        raise err

    @overload
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: genshin.models.SessionMMTResult,
        ticket: None = ...,
    ) -> genshin.models.AppLoginResult | genshin.models.ActionTicket: ...

    @overload
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: None = ...,
        ticket: genshin.models.ActionTicket,
    ) -> genshin.models.AppLoginResult: ...

    @overload
    async def os_app_login(
        self, email: str, password: str, *, mmt_result: None = ..., ticket: None = ...
    ) -> (
        genshin.models.AppLoginResult | genshin.models.SessionMMT | genshin.models.ActionTicket
    ): ...

    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: genshin.models.SessionMMTResult | None = None,
        ticket: genshin.models.ActionTicket | None = None,
    ) -> genshin.models.AppLoginResult | genshin.models.SessionMMT | genshin.models.ActionTicket:
        api_url = next(proxy_api_rotator)

        if api_url == "LOCAL":
            if mmt_result is not None:
                return await self._app_login(email, password, mmt_result=mmt_result)
            if ticket is not None:
                return await self._app_login(email, password, ticket=ticket)
            return await self._app_login(email, password)

        payload = {
            "email": genshin.utility.encrypt_credentials(email, 1),
            "password": genshin.utility.encrypt_credentials(password, 1),
        }
        if mmt_result is not None:
            payload["mmt_result"] = mmt_result.model_dump_json(by_alias=True)
        elif ticket is not None:
            payload["ticket"] = ticket.model_dump_json(by_alias=True)

        data = await self.request_proxy_api(api_url, "login", payload)
        retcode = data["retcode"]
        data_ = orjson.loads(data["data"])

        if retcode == -9999:
            return genshin.models.SessionMMT(**data_)
        if retcode == -9998:
            return genshin.models.ActionTicket(**data_)
        return genshin.models.AppLoginResult(**data_)


class GenshinClient(ProxyGenshinClient):
    def __init__(self, account: HoyoAccount) -> None:
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
        )
        self._account = account

    async def request_proxy_api(
        self, api_url: str, endpoint: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        account = self._account
        payload["cookies"] = account.cookies
        payload["uid"] = account.uid

        data = await super().request_proxy_api(api_url, endpoint, payload)
        if (cookies := data.get("cookies")) and account.cookies != cookies:
            account.cookies = decrypt_string(cookies)
            await account.save(update_fields=("cookies",))
        return data

    def set_lang(self, locale: Locale) -> None:
        if self._account.game is Game.STARRAIL and locale is Locale.turkish:
            self.lang = "en-us"
            return

        self.lang = (
            "zh-cn"
            if self.region is genshin.Region.CHINESE
            else LOCALE_TO_GPY_LANG.get(locale, "en-us")
        )

    def get_daily_reward_embed(
        self, daily_reward: genshin.models.DailyReward, locale: Locale, *, blur: bool
    ) -> DefaultEmbed:
        return (
            DefaultEmbed(
                locale,
                title=LocaleStr(key="reward_claimed_title"),
                description=f"{daily_reward.name} x{daily_reward.amount}",
            )
            .set_thumbnail(url=daily_reward.icon)
            .add_acc_info(self._account, blur=blur)
            .set_footer(text=LocaleStr(key="checkin_reward_embed_footer"))
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
        fields = await self.get_lineup_fields(use_cache=False)
        pc_icons = {str(character.id): character.pc_icon for character in fields.characters}
        await JSONFile.write("pc_icons.json", pc_icons)

    @staticmethod
    async def convert_gi_character(
        character: genshin.models.GenshinDetailCharacter,
    ) -> models.HoyolabGICharacter:
        """Convert GenshinDetailCharacter from gpy to HoyolabGICharacter that's used for drawing cards."""
        weapon = models.HoyolabGIWeapon(
            name=character.weapon.name,
            icon=character.weapon.icon,
            refinement=character.weapon.refinement,
            level=character.weapon.level,
            max_level=hakushin.utils.get_max_level_from_ascension(
                character.weapon.ascension, hakushin.Game.GI
            ),
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
            models.HoyolabGIConst(icon=const.icon, unlocked=const.activated)
            for const in character.constellations
        ]

        artifacts = [
            models.HoyolabGIArtifact(
                icon=artifact.icon,
                rarity=artifact.rarity,
                level=artifact.level,
                main_stat=models.HoyolabGIStat(
                    type=convert_fight_prop(artifact.main_stat.info.type),
                    formatted_value=artifact.main_stat.value,
                ),
                sub_stats=[
                    models.HoyolabGIStat(
                        type=convert_fight_prop(sub_stat.info.type), formatted_value=sub_stat.value
                    )
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
            prop = next(
                (prop for prop in character.element_properties if prop.info.type == prop_id), None
            )
            if prop is None:
                msg = f"Couldn't find the highest damage bonus stat for {character.name} ({character.element})"
                raise ValueError(msg)

            highest_dmg_bonus_stat = models.HoyolabGIStat(
                type=convert_fight_prop(prop_id), formatted_value=prop.final
            )

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
                hakushin.utils.get_ascension_from_level(character.level, True, hakushin.Game.GI),
                hakushin.Game.GI,
            ),
            icon=models.HoyolabGICharacterIcon(gacha=character.gacha_art),
        )

    @staticmethod
    def convert_hsr_character(
        character: genshin.models.StarRailDetailCharacter,
        property_info: dict[str, genshin.models.PropertyInfo],
    ) -> models.HoyolabHSRCharacter:
        """Convert StarRailDetailCharacter from gpy to HoyolabHSRCharacter that's used for drawing cards."""
        prop_icons: dict[int, str] = {
            prop.property_type: prop.icon for prop in property_info.values()
        }

        light_cone = (
            models.LightCone(
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
                models.Stat(
                    icon=prop_icons[prop.property_type],
                    formatted_value=prop.final,
                    type=prop.property_type,
                )
                for prop in character.properties
            ],
            traces=[
                models.Trace(anchor=skill.anchor, icon=skill.item_url, level=skill.level)
                for skill in character.skills
            ],
            max_level=hakushin.utils.get_max_level_from_ascension(
                hakushin.utils.get_ascension_from_level(character.level, True, hakushin.Game.HSR),
                hakushin.Game.HSR,
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
            live_data = dict(
                await self.get_genshin_detailed_characters(self._account.uid, return_raw_data=True)
            )
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
                live_data = (await super().get_zzz_agent_info(character_id)).model_dump(
                    by_alias=True
                )
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
        self, codes: Sequence[str], *, locale: Locale, blur: bool = True, api_url: str | None = None
    ) -> DefaultEmbed:
        """Redeem multiple codes and return an embed with the results."""
        results: list[tuple[str, str, bool]] = []

        for code in codes:
            if not code:
                continue

            msg, success = await self.redeem_code(code.strip(), locale=locale, api_url=api_url)
            results.append((code, msg, success))
            await asyncio.sleep(6)

        return self.get_redeem_codes_embed(results, locale=locale, blur=blur)

    def get_redeem_codes_embed(
        self, results: list[tuple[str, str, bool]], *, locale: Locale, blur: bool
    ) -> DefaultEmbed:
        # get the first 25 results
        results = results[:25]
        embed = DefaultEmbed(
            locale, title=LocaleStr(key="redeem_command_embed.title")
        ).add_acc_info(self._account, blur=blur)
        for result in results:
            name = f"{'✅' if result[2] else '❌'} {result[0]}"
            embed.add_field(name=name, value=result[1])

        return embed

    async def _add_to_redeemed_codes(self, code: str) -> None:
        self._account.redeemed_codes.append(code)
        self._account.redeemed_codes = list(set(self._account.redeemed_codes))
        await self._account.save(update_fields=("redeemed_codes",))

    async def redeem_code(
        self, code: str, *, locale: Locale, api_url: str | None = None
    ) -> tuple[str, bool]:
        """Redeem a code, return a message and a boolean indicating success."""
        api_url = api_url or next(proxy_api_rotator)

        success = False
        try:
            if api_url == "LOCAL":
                await super().redeem_code(code)
            else:
                await self.request_proxy_api(api_url, "redeem", {"code": code})
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
                    return await self.redeem_code(code, locale=locale)
            else:
                # cookie token can't be refreshed
                raise genshin.GenshinException({"retcode": 999}) from e
        except genshin.RedemptionCooldown:
            # sleep then retry
            await asyncio.sleep(6)
            return await self.redeem_code(code, locale=locale)
        except Exception as e:
            embed, recognized = get_error_embed(e, locale)
            if not recognized:
                raise

            if isinstance(e, genshin.RedemptionClaimed | genshin.RedemptionInvalid):
                await self._add_to_redeemed_codes(code)
            if isinstance(e, genshin.GenshinException) and e.retcode == -2006:
                # Code reached max redemption limit
                await self._add_to_redeemed_codes(code)

            assert embed.title is not None
            if embed.description is None:
                return embed.title, success
            return f"{embed.title}\n{embed.description}", success
        else:
            await self._add_to_redeemed_codes(code)
            success = True
            msg = LocaleStr(key="redeem_code.success").translate(locale)

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
            endpoint,
            game=game,
            method=method,
            lang=lang,
            params=params,
            headers=headers,
            challenge=challenge,
            **kwargs,
        )

    @overload
    async def get_notes_(self, game: Literal[genshin.Game.GENSHIN]) -> genshin.models.Notes: ...

    @overload
    async def get_notes_(
        self, game: Literal[genshin.Game.STARRAIL]
    ) -> genshin.models.StarRailNote: ...

    @overload
    async def get_notes_(self, game: Literal[genshin.Game.ZZZ]) -> genshin.models.ZZZNotes: ...

    @overload
    async def get_notes_(
        self, game: Literal[genshin.Game.HONKAI]
    ) -> genshin.models.HonkaiNotes: ...

    async def get_notes_(
        self,
        game: Literal[
            genshin.Game.GENSHIN, genshin.Game.STARRAIL, genshin.Game.ZZZ, genshin.Game.HONKAI
        ],
    ) -> (
        genshin.models.Notes
        | genshin.models.StarRailNote
        | genshin.models.ZZZNotes
        | genshin.models.HonkaiNotes
    ):
        uid = self._account.uid
        api_url = next(proxy_api_rotator)

        if api_url == "LOCAL":
            if game is genshin.Game.GENSHIN:
                return await super().get_genshin_notes(uid)
            if game is genshin.Game.STARRAIL:
                return await super().get_starrail_notes(uid)
            if game is genshin.Game.ZZZ:
                return await super().get_zzz_notes(uid)
            if game is genshin.Game.HONKAI:
                return await super().get_honkai_notes(uid)

        payload = {
            "cookies": self._account.cookies,
            "uid": uid,
            "lang": self.lang,
            "game": game.value,
        }
        data = await self.request_proxy_api(api_url, "notes", payload)

        if game is genshin.Game.GENSHIN:
            return genshin.models.Notes(**data["data"])
        if game is genshin.Game.STARRAIL:
            return genshin.models.StarRailNote(**data["data"])
        if game is genshin.Game.ZZZ:
            return genshin.models.ZZZNotes(**data["data"])
        if game is genshin.Game.HONKAI:
            return genshin.models.HonkaiNotes(**data["data"])

    async def get_genshin_notes(self) -> genshin.models.Notes:
        return await self.get_notes_(genshin.Game.GENSHIN)

    async def get_starrail_notes(self) -> genshin.models.StarRailNote:
        return await self.get_notes_(genshin.Game.STARRAIL)

    async def get_zzz_notes(self) -> genshin.models.ZZZNotes:
        return await self.get_notes_(genshin.Game.ZZZ)

    async def get_honkai_notes(self) -> genshin.models.HonkaiNotes:
        return await self.get_notes_(genshin.Game.HONKAI)

    async def finish_mimo_task(
        self, task_id: int, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> None:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL":
            return await super().finish_mimo_task(task_id, game_id=game_id, version_id=version_id)

        payload = {
            "cookies": self._account.cookies,
            "game_id": game_id,
            "version_id": version_id,
            "task_id": task_id,
        }
        await self.request_proxy_api(api_url, "mimo/finish_task", payload)

    async def claim_mimo_task_reward(
        self, task_id: int, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> None:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL":
            return await super().claim_mimo_task_reward(
                task_id, game_id=game_id, version_id=version_id
            )

        payload = {
            "cookies": self._account.cookies,
            "game_id": game_id,
            "version_id": version_id,
            "task_id": task_id,
        }
        await self.request_proxy_api(api_url, "mimo/claim_reward", payload)

    async def buy_mimo_shop_item(
        self, item_id: int, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> str:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL":
            return await super().buy_mimo_shop_item(item_id, game_id=game_id, version_id=version_id)

        payload = {
            "cookies": self._account.cookies,
            "game_id": game_id,
            "version_id": version_id,
            "item_id": item_id,
        }
        data = await self.request_proxy_api(api_url, "mimo/buy_item", payload)
        return data["code"]

    async def get_mimo_tasks(
        self, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> Sequence[genshin.models.MimoTask]:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL":
            return await super().get_mimo_tasks(game_id=game_id, version_id=version_id)

        payload = {"cookies": self._account.cookies, "game_id": game_id, "version_id": version_id}
        data = await self.request_proxy_api(api_url, "mimo/tasks", payload)
        return [genshin.models.MimoTask(**orjson.loads(task)) for task in data["tasks"]]

    async def get_mimo_shop_items(
        self, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> Sequence[genshin.models.MimoShopItem]:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL":
            return await super().get_mimo_shop_items(game_id=game_id, version_id=version_id)

        payload = {"cookies": self._account.cookies, "game_id": game_id, "version_id": version_id}
        data = await self.request_proxy_api(api_url, "mimo/shop", payload)
        return [genshin.models.MimoShopItem(**orjson.loads(item)) for item in data["items"]]

    async def finish_and_claim_mimo_tasks(
        self, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> tuple[list[genshin.models.MimoTask], list[genshin.models.MimoTask]]:
        finished: list[genshin.models.MimoTask] = []
        claimed: list[genshin.models.MimoTask] = []

        tasks = await self.get_mimo_tasks(game_id=game_id, version_id=version_id)

        for task in tasks:
            if task.status is not genshin.models.MimoTaskStatus.ONGOING:
                continue

            if task.type in {
                genshin.models.MimoTaskType.FINISHABLE,
                genshin.models.MimoTaskType.TRAILER,
                genshin.models.MimoTaskType.VISIT,
            }:
                try:
                    await self.finish_mimo_task(
                        task.id, game_id=game_id, version_id=version_id, api_url=api_url
                    )
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise
                finished.append(task)

            elif task.type is genshin.models.MimoTaskType.COMMENT:
                url_data = orjson.loads(task.jump_url)
                args: dict[str, str] | None = url_data.get("args")
                if args is None:
                    continue

                post_id: str | None = args.get("post_id")
                if post_id is not None:
                    reply_id = await self.reply_to_post(
                        random.choice(POST_REPLIES), post_id=int(post_id)
                    )
                    await asyncio.sleep(2)
                    await self.delete_reply(reply_id=reply_id, post_id=int(post_id))
                    await asyncio.sleep(2)
                    finished.append(task)

                topic_id: str | None = args.get("topic_id")
                if topic_id is not None:
                    await self.join_topic(int(topic_id))
                    await asyncio.sleep(2)
                    await self.leave_topic(int(topic_id))
                    await asyncio.sleep(2)
                    finished.append(task)

        if len(finished) > 0:
            tasks = await self.get_mimo_tasks(game_id=game_id, version_id=version_id)

        for task in tasks:
            if task.status is genshin.models.MimoTaskStatus.FINISHED:
                try:
                    await self.claim_mimo_task_reward(
                        task.id, game_id=game_id, version_id=version_id, api_url=api_url
                    )
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise

                claimed.append(task)

        return finished, claimed

    async def buy_mimo_valuables(
        self, *, game_id: int, version_id: int, api_url: str | None = None
    ) -> list[tuple[genshin.models.MimoShopItem, str]]:
        bought: list[tuple[genshin.models.MimoShopItem, str]] = []

        points = await self.get_mimo_point_count()
        items = await self.get_mimo_shop_items(game_id=game_id, version_id=version_id)
        item_mi18n = {item.id: item for item in items}

        self.lang = "en-us"
        en_items = await self.get_mimo_shop_items(game_id=game_id, version_id=version_id)

        keywords = ("Stellar Jades", "Polychrome")
        for item in en_items:
            if (
                any(keyword in item.name for keyword in keywords)
                and item.status is genshin.models.MimoShopItemStatus.EXCHANGEABLE
                and item.cost <= points
            ):
                try:
                    code = await self.buy_mimo_shop_item(
                        item.id, game_id=game_id, version_id=version_id, api_url=api_url
                    )
                except genshin.GenshinException as e:
                    if e.retcode == -502005:  # Insufficient points
                        continue
                    raise

                bought.append((item_mi18n[item.id], code))
                points = await self.get_mimo_point_count()

        return bought

    async def claim_daily_reward(
        self, *, api_url: str | None = None, challenge: dict[str, str] | None = None
    ) -> genshin.models.DailyReward:
        api_url = api_url or next(proxy_api_rotator)
        if api_url == "LOCAL" or challenge is not None:
            return await super().claim_daily_reward(challenge=challenge)

        data = await self.request_proxy_api(api_url, "checkin", {})

        # Correct reward amount
        monthly_rewards = await self.get_monthly_rewards()
        reward = next((r for r in monthly_rewards if r.icon == data["data"]["icon"]), None)
        if reward is None:
            reward = genshin.models.DailyReward(**data["data"])
        return reward
