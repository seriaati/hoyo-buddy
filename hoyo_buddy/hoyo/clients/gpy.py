from __future__ import annotations

import asyncio
import itertools
import random
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, overload

import aiohttp
import enka
import genshin
import hakushin
import orjson
from discord import Locale
from loguru import logger
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from hoyo_buddy import models
from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    AMBR_TRAVELER_ID_TO_ENKA_TRAVELER_ID,
    AMBR_UI_URL,
    DMG_BONUS_IDS,
    ELEMENT_TO_BONUS_PROP_ID,
    GPY_LANG_TO_LOCALE,
    HB_GAME_TO_GPY_GAME,
    LOCALE_TO_GPY_LANG,
    PLAYER_BOY_GACHA_ART,
    PLAYER_GIRL_GACHA_ART,
    POST_REPLIES,
    PROXY_APIS,
    contains_traveler_id,
    convert_fight_prop,
)
from hoyo_buddy.db import EnkaCache, HoyoAccount, JSONFile
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, GenshinElement
from hoyo_buddy.exceptions import HoyoBuddyError, ProxyAPIError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_now, set_or_update_dict
from hoyo_buddy.web_app.utils import decrypt_string

if TYPE_CHECKING:
    import datetime
    from collections.abc import Mapping, Sequence

    from hoyo_buddy.types import ProxyAPI


env = CONFIG.env

MIMO_TASK_DELAY = 1.0
MIMO_COMMUNITY_TASK_DELAY = 2.0
API_TOKEN = CONFIG.daily_checkin_api_token

PROXY_APIS_ = (*PROXY_APIS.keys(), "LOCAL")
proxy_api_rotator = itertools.cycle(PROXY_APIS_)

API_ERROR_COUNTS = dict.fromkeys(PROXY_APIS_, 0)
"""Track number of login ratelimit errors for each API."""
API_DISABLE_DATETIMES: dict[ProxyAPI | Literal["LOCAL"], datetime.datetime] = {}
"""Track when an API was disabled."""

API_DISABLE_THRESHOLD = 5
"""Disable an API after this many login ratelimit errors."""
API_DISABLE_DURATION = 3600  # 1 hour
"""How long the API should be disabled."""


class MimoClaimTaksResult(NamedTuple):
    finished: list[genshin.models.MimoTask]
    claimed_points: int
    all_claimed: bool


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

        self.api_url_iterator: itertools.cycle[str] | None = None
        """For request_proxy_api."""
        self.api_name_iterator: itertools.cycle[ProxyAPI | Literal["LOCAL"]] | None = None
        """For os_app_login."""

    @staticmethod
    def _disable_api(api_name: ProxyAPI | Literal["LOCAL"]) -> None:
        if api_name in API_DISABLE_DATETIMES:
            return
        logger.debug(f"Disabling {api_name} API")
        API_DISABLE_DATETIMES[api_name] = get_now()

    @staticmethod
    def _enable_api(api_name: ProxyAPI | Literal["LOCAL"]) -> None:
        if api_name not in API_DISABLE_DATETIMES:
            return
        logger.debug(f"Enabling {api_name} API")
        API_DISABLE_DATETIMES.pop(api_name)

    @staticmethod
    def _is_disabled_api(api_name: ProxyAPI | Literal["LOCAL"]) -> bool:
        if api_name not in API_DISABLE_DATETIMES:
            return False
        return (get_now() - API_DISABLE_DATETIMES[api_name]).total_seconds() < API_DISABLE_DURATION

    @staticmethod
    def _get_available_apis() -> list[ProxyAPI | Literal["LOCAL"]]:
        for api, dt in API_DISABLE_DATETIMES.items():
            if (get_now() - dt).total_seconds() >= API_DISABLE_DURATION:
                ProxyGenshinClient._enable_api(api)
        return [api for api in PROXY_APIS_ if not ProxyGenshinClient._is_disabled_api(api)]

    @staticmethod
    def _before_api_retry(retry_state: RetryCallState) -> None:
        if retry_state.attempt_number > 1:
            retry_state.kwargs["retrying"] = True

    @staticmethod
    def _login_ratelimit_exception(exc: BaseException) -> bool:
        return isinstance(exc, genshin.GenshinException) and exc.retcode == -3006

    @retry(
        stop=stop_after_attempt(len(PROXY_APIS)),
        wait=wait_random_exponential(multiplier=0.5, min=0.5),
        retry=retry_if_exception_type((TimeoutError, aiohttp.ClientError, ProxyAPIError)),
        reraise=True,
        before=_before_api_retry,
    )
    async def request_proxy_api(
        self, api_name: ProxyAPI, endpoint: str, payload: dict[str, Any], *, retrying: bool = False
    ) -> dict[str, Any]:
        if not retrying:
            api_url = PROXY_APIS[api_name]
            fallback_urls = [url for name, url in PROXY_APIS.items() if name != api_name]
            self.api_url_iterator = itertools.cycle(fallback_urls)
        else:
            if self.api_url_iterator is None:
                msg = "API URL iterator is None when retrying"
                raise ValueError(msg)
            api_url = next(self.api_url_iterator)

        payload["lang"] = self.lang
        payload["region"] = self.region.value
        if self.game is not None:
            payload["game"] = self.game.value

        sanitized_payload = {k: v for k, v in payload.items() if k not in {"cookies", "token"}}
        logger.debug(f"Requesting {api_url}/{endpoint}/ with payload: {sanitized_payload}")

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{api_url}/{endpoint}/",
                json=payload,
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            ) as resp,
        ):
            if resp.status in {200, 400, 500}:
                data = await resp.json()

                if resp.status == 200:
                    return data
                if resp.status == 400:
                    genshin.raise_for_retcode(data)

                message = data.get("message", "Unknown proxy API error")
                raise ProxyAPIError(api_url, resp.status, message=message)

            raise ProxyAPIError(api_url, resp.status)

    @overload
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: genshin.models.SessionMMTResult,
        ticket: None = ...,
        retrying: bool = ...,
    ) -> genshin.models.AppLoginResult | genshin.models.ActionTicket: ...

    @overload
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: None = ...,
        ticket: genshin.models.ActionTicket,
        retrying: bool = ...,
    ) -> genshin.models.AppLoginResult: ...

    @overload
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: None = ...,
        ticket: None = ...,
        retrying: bool = ...,
    ) -> (
        genshin.models.AppLoginResult | genshin.models.SessionMMT | genshin.models.ActionTicket
    ): ...

    @retry(
        stop=stop_after_attempt(len(PROXY_APIS_)),
        wait=wait_random_exponential(multiplier=0.5, min=0.5),
        retry=retry_if_exception(_login_ratelimit_exception),
        reraise=True,
        before=_before_api_retry,
    )
    async def os_app_login(
        self,
        email: str,
        password: str,
        *,
        mmt_result: genshin.models.SessionMMTResult | None = None,
        ticket: genshin.models.ActionTicket | None = None,
        retrying: bool = False,
    ) -> genshin.models.AppLoginResult | genshin.models.SessionMMT | genshin.models.ActionTicket:
        if not retrying:
            # First attempt
            api_name = next(proxy_api_rotator)
            fallback_apis = [api for api in PROXY_APIS_ if api != api_name]
            self.api_name_iterator = itertools.cycle(fallback_apis)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            if self.api_name_iterator is None:
                msg = "API name iterator is None when retrying"
                raise ValueError(msg)
            api_name = next(self.api_name_iterator)

        while API_ERROR_COUNTS[api_name] >= API_DISABLE_THRESHOLD:
            self._disable_api(api_name)

            available_apis = self._get_available_apis()
            logger.debug(f"Available APIs: {available_apis}")
            if not available_apis:
                msg = "System capacity reached, try again later"
                raise ValueError(msg)

            api_name = random.choice(available_apis)

        try:
            if api_name == "LOCAL":
                if mmt_result is not None:
                    result = await self._app_login(email, password, mmt_result=mmt_result)
                elif ticket is not None:
                    result = await self._app_login(email, password, ticket=ticket)
                else:
                    result = await self._app_login(email, password)
            else:
                payload = {
                    "email": genshin.utility.encrypt_credentials(email, 1),
                    "password": genshin.utility.encrypt_credentials(password, 1),
                }
                if mmt_result is not None:
                    payload["mmt_result"] = mmt_result.model_dump_json(by_alias=True)
                elif ticket is not None:
                    payload["ticket"] = ticket.model_dump_json(by_alias=True)

                data = await self.request_proxy_api(api_name, "login", payload)
                retcode = data["retcode"]
                data_ = orjson.loads(data["data"])

                if retcode == -9999:
                    result = genshin.models.SessionMMT(**data_)
                elif retcode == -9998:
                    result = genshin.models.ActionTicket(**data_)
                else:
                    result = genshin.models.AppLoginResult(**data_)
        except Exception as e:
            if self._login_ratelimit_exception(e):
                API_ERROR_COUNTS[api_name] += 1
            raise
        else:
            API_ERROR_COUNTS[api_name] = 0
            API_DISABLE_DATETIMES.pop(api_name, None)
            return result


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
        self, api_name: ProxyAPI, endpoint: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        account = self._account

        payload = payload or {}
        payload["cookies"] = account.cookies
        payload["uid"] = account.uid

        data = await super().request_proxy_api(api_name, endpoint, payload)
        if cookies := data.get("cookies"):
            decrypted_cookies = decrypt_string(cookies)
            if account.cookies != decrypted_cookies:
                account.cookies = decrypted_cookies
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
            prop_id = ELEMENT_TO_BONUS_PROP_ID[
                GenshinElement.ANEMO
                if character.element == "None"
                else GenshinElement(character.element)
            ]
            prop = next(
                (prop for prop in character.element_properties if prop.info.type == prop_id), None
            )
            if prop is None:
                msg = f"Couldn't find the highest damage bonus stat for {character.name} ({character.element})"
                raise ValueError(msg)

            highest_dmg_bonus_stat = models.HoyolabGIStat(
                type=convert_fight_prop(prop_id), formatted_value=prop.final
            )

        costume: models.HoyolabGICostume | None = None
        async with enka.GenshinClient() as client:
            if character.costumes:
                costumes: dict[str, dict[str, Any]] | None = client._assets.character_data[
                    str(character.id)
                ].get("Costumes")
                if costumes:
                    chara_costume = character.costumes[0]
                    costume_data = costumes.get(str(chara_costume.id))
                    if costume_data:
                        costume = models.HoyolabGICostume(
                            icon=models.HoyolabGICharacterIcon(
                                gacha=AMBR_UI_URL.format(filename=costume_data["art"])
                            )
                        )
            talent_order = client._assets.character_data[str(character.id)]["SkillOrder"]

        if "10000005" in str(character.id):  # PlayerBoy
            gacha_art = PLAYER_BOY_GACHA_ART
        elif "10000007" in str(character.id):  # PlayerGirl
            gacha_art = PLAYER_GIRL_GACHA_ART
        else:
            gacha_art = character.gacha_art

        icon = models.HoyolabGICharacterIcon(gacha=gacha_art)

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
            icon=icon,
            costume=costume,
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
                rarity=character.equip.rarity,
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
            rarity=character.rarity,
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
            eidolons=[
                models.Eidolon(icon=eidolon.icon, unlocked=eidolon.is_unlocked)
                for eidolon in character.ranks
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

    async def get_zzz_agents(
        self, uid: int | None = None
    ) -> Sequence[genshin.models.ZZZPartialAgent]:
        cache, _ = await EnkaCache.get_or_create(uid=self.uid)
        agents = await super().get_zzz_agents(uid)
        for agent in agents:
            set_or_update_dict(
                cache.extras,
                f"{agent.id}-hoyolab",
                {"live": True, "locale": GPY_LANG_TO_LOCALE[self.lang].value},
            )
        await cache.save(update_fields=("extras",))
        return agents

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
        self,
        codes: Sequence[str],
        *,
        locale: Locale,
        blur: bool = True,
        api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL",
        skip_redeemed: bool = True,
    ) -> DefaultEmbed | None:
        """Redeem multiple codes and return an embed with the results."""
        if not codes:
            return None

        results: list[tuple[str, str, bool]] = []
        for code in codes:
            if not code or (code in self._account.redeemed_codes and skip_redeemed):
                continue

            msg, success = await self.redeem_code(code.strip(), locale=locale, api_name=api_name)
            results.append((code, msg, success))
            await asyncio.sleep(6)

        if not results:
            return None
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
        self, code: str, *, locale: Locale, api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL"
    ) -> tuple[str, bool]:
        """Redeem a code, return a message and a boolean indicating success."""
        success = False
        try:
            if api_name == "LOCAL":
                await super().redeem_code(code)
            else:
                await self.request_proxy_api(api_name, "redeem", {"code": code})
        except genshin.InvalidCookies as e:
            # cookie token is invalid
            if "stoken" in self._account.dict_cookies and "ltmid_v2" in self._account.dict_cookies:
                # cookie token can be refreshed
                try:
                    await self.update_cookie_token()
                except genshin.InvalidCookies as e:
                    # cookie token refresh failed
                    raise genshin.GenshinException({"retcode": 1000}) from e
                else:
                    # cookie token refresh succeeded, redeem code again
                    await asyncio.sleep(6)
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
            if "HoYo API Error" in embed.title:
                return embed.description, success
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

        data = await self.request_proxy_api(api_url, "notes")

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
        self,
        task_id: int,
        *,
        game_id: int,
        version_id: int,
        api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL",
    ) -> None:
        if api_name == "LOCAL":
            return await super().finish_mimo_task(task_id, game_id=game_id, version_id=version_id)

        payload = {"game_id": game_id, "version_id": version_id, "task_id": task_id}
        await self.request_proxy_api(api_name, "mimo/finish_task", payload)

    async def claim_mimo_task_reward(
        self,
        task_id: int,
        *,
        game_id: int,
        version_id: int,
        api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL",
    ) -> None:
        if api_name == "LOCAL":
            return await super().claim_mimo_task_reward(
                task_id, game_id=game_id, version_id=version_id
            )

        payload = {"game_id": game_id, "version_id": version_id, "task_id": task_id}
        await self.request_proxy_api(api_name, "mimo/claim_reward", payload)

    async def buy_mimo_shop_item(
        self,
        item_id: int,
        *,
        game_id: int,
        version_id: int,
        api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL",
    ) -> str:
        if api_name == "LOCAL":
            return await super().buy_mimo_shop_item(item_id, game_id=game_id, version_id=version_id)

        payload = {"game_id": game_id, "version_id": version_id, "item_id": item_id}
        data = await self.request_proxy_api(api_name, "mimo/buy_item", payload)
        return data["code"]

    async def get_mimo_tasks(
        self, *, game_id: int, version_id: int, api_name: ProxyAPI | Literal["LOCAL"] = "RENDER4"
    ) -> Sequence[genshin.models.MimoTask]:
        try:
            if api_name == "LOCAL":
                return await super().get_mimo_tasks(game_id=game_id, version_id=version_id)

            payload = {"game_id": game_id, "version_id": version_id}
            data = await self.request_proxy_api(api_name, "mimo/tasks", payload)
            return [genshin.models.MimoTask(**orjson.loads(task)) for task in data["tasks"]]
        except genshin.GenshinException as e:
            if e.retcode == -510001:  # Invalid fields in calculation
                raise HoyoBuddyError(
                    message=LocaleStr(
                        key="gi_mimo_start_desc",
                        url="https://act.hoyolab.com/ys/event/bbs-event-20240828mimo/index.html",
                    )
                ) from e
            raise

    async def get_mimo_shop_items(
        self, *, game_id: int, version_id: int, api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL"
    ) -> Sequence[genshin.models.MimoShopItem]:
        if api_name == "LOCAL":
            return await super().get_mimo_shop_items(game_id=game_id, version_id=version_id)

        payload = {"game_id": game_id, "version_id": version_id}
        data = await self.request_proxy_api(api_name, "mimo/shop", payload)
        return [genshin.models.MimoShopItem(**orjson.loads(item)) for item in data["items"]]

    async def finish_and_claim_mimo_tasks(
        self, *, game_id: int, version_id: int, api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL"
    ) -> MimoClaimTaksResult:
        finished_tasks: list[genshin.models.MimoTask] = []
        finished = False  # True if at least one task was finished
        claimed_points = 0

        tasks = await self.get_mimo_tasks(game_id=game_id, version_id=version_id, api_name=api_name)

        for task in tasks:
            if task.status is not genshin.models.MimoTaskStatus.ONGOING:
                continue

            if task.type in {
                genshin.models.MimoTaskType.FINISHABLE,
                genshin.models.MimoTaskType.TRAILER,
                genshin.models.MimoTaskType.VISIT,
                genshin.models.MimoTaskType.VIEW_TOPIC,
            }:
                try:
                    await self.finish_mimo_task(
                        task.id, game_id=game_id, version_id=version_id, api_name=api_name
                    )
                    await asyncio.sleep(MIMO_TASK_DELAY)
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise
                finished = True

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
                    await asyncio.sleep(MIMO_COMMUNITY_TASK_DELAY)
                    await self.delete_reply(reply_id=reply_id, post_id=int(post_id))
                    await asyncio.sleep(MIMO_COMMUNITY_TASK_DELAY)
                    finished = True

                topic_id: str | None = args.get("topic_id")
                if topic_id is not None:
                    await self.join_topic(int(topic_id))
                    await asyncio.sleep(MIMO_COMMUNITY_TASK_DELAY)
                    await self.leave_topic(int(topic_id))
                    await asyncio.sleep(MIMO_COMMUNITY_TASK_DELAY)
                    finished = True

        if finished:
            tasks = await self.get_mimo_tasks(
                game_id=game_id, version_id=version_id, api_name=api_name
            )

        for task in tasks:
            if task.status is genshin.models.MimoTaskStatus.FINISHED:
                try:
                    await self.claim_mimo_task_reward(
                        task.id, game_id=game_id, version_id=version_id, api_name=api_name
                    )
                    await asyncio.sleep(MIMO_TASK_DELAY)
                except genshin.GenshinException as e:
                    if e.retcode == -500001:  # Invalid fields in calculation
                        continue
                    raise

                finished_tasks.append(task)
                claimed_points += task.point

        return MimoClaimTaksResult(
            finished_tasks,
            claimed_points,
            all(task.status is genshin.models.MimoTaskStatus.CLAIMED for task in tasks),
        )

    async def buy_mimo_valuables(
        self, *, game_id: int, version_id: int, api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL"
    ) -> list[tuple[genshin.models.MimoShopItem, str]]:
        result: list[tuple[genshin.models.MimoShopItem, str]] = []
        bought: list[tuple[int, str]] = []

        original_lang = self.lang[:]
        points = await self.get_mimo_point_count()
        await asyncio.sleep(0.5)

        self.lang = "en-us"
        en_items = await self.get_mimo_shop_items(
            game_id=game_id, version_id=version_id, api_name=api_name
        )
        await asyncio.sleep(0.5)

        # Sort items from most expensive to least expensive
        en_items = sorted(en_items, key=lambda item: item.cost, reverse=True)

        keywords = ("Stellar Jades", "Polychrome")
        for item in en_items:
            if (
                any(keyword in item.name for keyword in keywords)
                and item.status is genshin.models.MimoShopItemStatus.EXCHANGEABLE
                and item.cost <= points
            ):
                try:
                    code = await self.buy_mimo_shop_item(
                        item.id, game_id=game_id, version_id=version_id, api_name=api_name
                    )
                    await asyncio.sleep(0.5)
                except genshin.GenshinException as e:
                    if e.retcode == -502005:  # Insufficient points
                        continue
                    raise

                bought.append((item.id, code))
                points -= item.cost

        if bought:
            self.lang = original_lang
            if original_lang != "en-us":
                items = await self.get_mimo_shop_items(
                    game_id=game_id, version_id=version_id, api_name=api_name
                )
            else:
                items = en_items

            item_mi18n = {item.id: item for item in items}
            result = [(item_mi18n[item_id], code) for item_id, code in bought]

        return result

    async def claim_daily_reward(
        self,
        *,
        api_name: ProxyAPI | Literal["LOCAL"] = "LOCAL",
        challenge: dict[str, str] | None = None,
    ) -> genshin.models.DailyReward:
        if api_name == "LOCAL" or challenge is not None:
            return await super().claim_daily_reward(challenge=challenge)

        data = await self.request_proxy_api(api_name, "checkin", {})

        # Correct reward amount
        monthly_rewards = await self.get_monthly_rewards()
        reward = next((r for r in monthly_rewards if r.icon == data["data"]["icon"]), None)
        if reward is None:
            reward = genshin.models.DailyReward(**data["data"])
        return reward
