from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from pydantic import ValidationError

from hoyo_buddy.constants import LOCALE_TO_HOYO_LANG
from hoyo_buddy.db.models import JSONFile
from hoyo_buddy.models.gacha_api import (
    GIGachaConfigResponse,
    HSRGachaCharacterListResponse,
    HSRGachaWeaponListResponse,
    ZZZGachaListResponse,
)

if TYPE_CHECKING:
    import aiohttp

GI_GACHA_API_URL = "https://sg-public-api.hoyolab.com/event/simulatoros/config?lang={lang}"
HSR_CHARACTER_GACHA_API_URL = "https://sg-public-api.hoyolab.com/event/rpgcalc/avatar/list?game=hkrpg&lang={lang}&tab_from=TabAll&page={page}&size=100"
HSR_WEAPON_GACHA_API_URL = "https://sg-public-api.hoyolab.com/event/rpgcalc/equipment/list?game=hkrpg&lang={lang}&tab_from=TabAll&page={page}&size=100"
ZZZ_GACHA_API_URL = (
    "https://starward-static.scighost.com/metadata/v1/zzz/ZZZGachaInfo.nap_global.{lang}.json"
)

GachaData = dict[str, dict[str, str]]


async def fetch_gi_gacha_data(session: aiohttp.ClientSession, lang: str) -> GachaData:
    url = GI_GACHA_API_URL.format(lang=lang)
    async with session.get(url) as resp:
        resp.raise_for_status()
        raw = await resp.json()

    try:
        response = GIGachaConfigResponse.model_validate(raw)
    except ValidationError:
        logger.warning(f"GI gacha data validation error for lang={lang!r}")
        return {}

    result: GachaData = {}
    for avatar in response.data.all_avatar:
        result[str(avatar.id)] = {"name": avatar.name, "icon": avatar.icon}
    for weapon in response.data.all_weapon:
        result[str(weapon.id)] = {"name": weapon.name, "icon": weapon.icon}
    return result


async def fetch_hsr_gacha_data(session: aiohttp.ClientSession, lang: str) -> GachaData:
    result: GachaData = {}

    page = 1
    while True:
        url = HSR_CHARACTER_GACHA_API_URL.format(lang=lang, page=page)
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.json()

        try:
            response = HSRGachaCharacterListResponse.model_validate(raw)
        except ValidationError:
            logger.warning(f"HSR gacha data validation error for lang={lang!r}, page={page}")
            break

        items = response.data.list
        for item in items:
            result[str(item.item_id)] = {"name": item.item_name, "icon": item.icon_url}

        if len(items) < 100:
            break
        page += 1

    page = 1
    while True:
        url = HSR_WEAPON_GACHA_API_URL.format(lang=lang, page=page)
        async with session.get(url) as resp:
            resp.raise_for_status()
            raw = await resp.json()

        try:
            response = HSRGachaWeaponListResponse.model_validate(raw)
        except ValidationError:
            logger.warning(f"HSR weapon gacha data validation error for lang={lang!r}, page={page}")
            break

        items = response.data.list
        for item in items:
            result[str(item.item_id)] = {"name": item.item_name, "icon": item.item_url}

        if len(items) < 100:
            break
        page += 1

    return result


async def fetch_zzz_gacha_data(session: aiohttp.ClientSession, lang: str) -> GachaData:
    url = ZZZ_GACHA_API_URL.format(lang=lang)
    async with session.get(url) as resp:
        resp.raise_for_status()
        raw = await resp.json(content_type=None)

    result: GachaData = {}
    try:
        response = ZZZGachaListResponse.model_validate(raw)
    except ValidationError:
        logger.warning(f"ZZZ gacha data validation error for lang={lang!r}")
        return result

    for item in response.data.list:
        result[str(item.id)] = {"name": item.name, "icon": item.icon}

    return result


async def update_gacha_data(session: aiohttp.ClientSession) -> None:
    langs = set(LOCALE_TO_HOYO_LANG.values())

    for lang in langs:
        try:
            gi_data = await fetch_gi_gacha_data(session, lang)
            if gi_data:
                await JSONFile.write(f"gi_gacha_data_{lang}.json", gi_data)
        except Exception:
            logger.exception(f"Failed to fetch GI gacha data for lang={lang!r}")

        try:
            hsr_data = await fetch_hsr_gacha_data(session, lang)
            if hsr_data:
                await JSONFile.write(f"hsr_gacha_data_{lang}.json", hsr_data)
        except Exception:
            logger.exception(f"Failed to fetch HSR gacha data for lang={lang!r}")

        try:
            zzz_data = await fetch_zzz_gacha_data(session, lang)
            if zzz_data:
                await JSONFile.write(f"zzz_gacha_data_{lang}.json", zzz_data)
        except Exception:
            logger.exception(f"Failed to fetch ZZZ gacha data for lang={lang!r}")
