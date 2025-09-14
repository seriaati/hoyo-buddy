from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.models.gacha import HSRBanner, ZZZBanner

if TYPE_CHECKING:
    import aiohttp

HSR_BANNER_URL = "https://starrailstation.com/api/v1/warp_config"
ZZZ_BANNER_URL = "https://zzz.rng.moe/api/v1/gacha/config?game=zzz"


async def fetch_hsr_banners(session: aiohttp.ClientSession) -> list[HSRBanner]:
    async with session.get(HSR_BANNER_URL) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return [
            HSRBanner(id=int(banner_id), **banner)
            for banner_id, banner in data.get("config", {}).get("banners", {}).items()
        ]


async def fetch_zzz_banners(session: aiohttp.ClientSession) -> list[ZZZBanner]:
    async with session.get(ZZZ_BANNER_URL) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return [
            ZZZBanner(id=int(banner_id), **banner)
            for banner_id, banner in data.get("data", {}).items()
        ]
