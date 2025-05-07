from __future__ import annotations

import enka

from hoyo_buddy.constants import LOCALE_TO_HSR_ENKA_LANG

from .base import BaseClient


class EnkaHSRClient(BaseClient):
    async def fetch_showcase(self, uid: int) -> enka.hsr.ShowcaseResponse:
        async with enka.HSRClient(
            lang=LOCALE_TO_HSR_ENKA_LANG.get(self._locale, enka.hsr.Language.ENGLISH),
            use_enka_icons=False,
            cache=enka.cache.SQLiteCache(),
        ) as client:
            return await client.fetch_showcase(uid)

    async def fetch_builds(self, owner: enka.Owner) -> dict[str, list[enka.hsr.Build]]:
        async with enka.HSRClient(
            lang=LOCALE_TO_HSR_ENKA_LANG.get(self._locale, enka.hsr.Language.ENGLISH),
            use_enka_icons=False,
            cache=enka.cache.SQLiteCache(),
        ) as client:
            return await client.fetch_builds(owner)
