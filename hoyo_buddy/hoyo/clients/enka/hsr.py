from __future__ import annotations

import logging

import enka

from ....constants import LOCALE_TO_HSR_ENKA_LANG
from .base import BaseClient

LOGGER_ = logging.getLogger(__name__)


class EnkaHSRClient(BaseClient):
    async def fetch_showcase(self, uid: int) -> tuple[enka.hsr.ShowcaseResponse, bool]:
        async with enka.HSRClient(
            lang=LOCALE_TO_HSR_ENKA_LANG.get(self._locale, enka.hsr.Language.ENGLISH)
        ) as client:
            return await super().fetch_showcase(client, uid)

    async def fetch_builds(self, owner: enka.Owner) -> dict[str, list[enka.hsr.Build]]:
        async with enka.HSRClient(
            lang=LOCALE_TO_HSR_ENKA_LANG.get(self._locale, enka.hsr.Language.ENGLISH)
        ) as client:
            return await client.fetch_builds(owner)
