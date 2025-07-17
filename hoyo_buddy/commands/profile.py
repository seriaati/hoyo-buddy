from __future__ import annotations

from typing import TYPE_CHECKING, overload

import enka
from genshin import GenshinException
from loguru import logger

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import LOCALE_TO_GI_ENKA_LANG
from hoyo_buddy.draw.card_data import CARD_DATA

from ..ui.hoyo.profile.view import ProfileView

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord
    from genshin.models import (
        PartialGenshinUserStats,
        RecordCard,
        StarRailUserStats,
        ZZZPartialAgent,
    )

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.models import HoyolabGICharacter
    from hoyo_buddy.types import Builds

    from ..enums import Game
    from ..models import HoyolabHSRCharacter

type EnkaData = enka.gi.ShowcaseResponse | enka.hsr.ShowcaseResponse | enka.zzz.ShowcaseResponse


class ProfileCommand:
    def __init__(
        self,
        *,
        uid: int,
        game: Game,
        account: HoyoAccount | None,
        character_ids: list[str | None],
        locale: Locale,
        user: discord.User | discord.Member,
    ) -> None:
        self._uid = uid
        self._game = game
        self._account = account
        self._character_ids = list({id_ for id_ in character_ids if id_ is not None})
        self._locale = locale
        self._user = user

        redis_url = CONFIG.redis_url
        if redis_url is None:
            logger.warning("Redis URL is not configured, using in-memory cache for Enka clients")
            self._enka_cache = enka.cache.MemoryCache()
        else:
            self._enka_cache = enka.cache.RedisCache(redis_url)

    @overload
    async def fetch_enka_data(
        self, client: enka.GenshinClient, uid: int, *, enka_hsr_down: bool = ...
    ) -> tuple[enka.gi.ShowcaseResponse | None, dict[str, list[enka.gi.Build]] | None]: ...
    @overload
    async def fetch_enka_data(
        self, client: enka.HSRClient, uid: int, *, enka_hsr_down: bool = ...
    ) -> tuple[enka.hsr.ShowcaseResponse | None, dict[str, list[enka.hsr.Build]] | None]: ...
    @overload
    async def fetch_enka_data(
        self, client: enka.ZZZClient, uid: int, *, enka_hsr_down: bool = ...
    ) -> tuple[enka.zzz.ShowcaseResponse | None, dict[str, list[enka.zzz.Build]] | None]: ...
    async def fetch_enka_data(
        self,
        client: enka.GenshinClient | enka.HSRClient | enka.ZZZClient,
        uid: int,
        *,
        enka_hsr_down: bool = False,
    ) -> tuple[EnkaData | None, Builds | None]:
        try:
            if isinstance(client, enka.HSRClient):
                enka_data = await client.fetch_showcase(uid, use_backup=enka_hsr_down)
            else:
                enka_data = await client.fetch_showcase(uid)
        except enka.errors.AssetKeyError:
            await client.update_assets()
            if isinstance(client, enka.HSRClient):
                enka_data = await client.fetch_showcase(uid, use_backup=enka_hsr_down)
            else:
                enka_data = await client.fetch_showcase(uid)
        except enka.errors.EnkaAPIError:
            if self._account is None:
                # enka fails and no hoyolab account provided, raise error
                raise
            enka_data = None

        if enka_data is not None and enka_data.owner is not None:
            builds = await client.fetch_builds(enka_data.owner)
        else:
            builds = None

        return enka_data, builds

    async def run_genshin(self) -> ProfileView:
        hoyolab_characters: list[HoyolabGICharacter] = []
        enka_data: enka.gi.ShowcaseResponse | None = None
        hoyolab_user: PartialGenshinUserStats | None = None
        builds = None

        lang = LOCALE_TO_GI_ENKA_LANG.get(self._locale, enka.gi.Language.ENGLISH)

        async with enka.GenshinClient(lang, cache=self._enka_cache) as client:
            enka_data, builds = await self.fetch_enka_data(client, self._uid)

        if self._account is not None:
            client = self._account.client
            client.set_lang(self._locale)
            try:
                if enka_data is None:
                    hoyolab_user = await client.get_partial_genshin_user(self._uid)
                hoyolab_characters = await client.get_hoyolab_gi_characters()
            except GenshinException:
                if enka_data is None:
                    # enka and hoyolab both failed, raise error
                    raise

        return ProfileView(
            self._uid,
            self._game,
            CARD_DATA.gi,
            character_ids=self._character_ids,
            hoyolab_gi_characters=hoyolab_characters,
            hoyolab_gi_user=hoyolab_user,
            genshin_data=enka_data,
            account=self._account,
            builds=builds,
            owner=enka_data.owner if enka_data is not None else None,
            author=self._user,
            locale=self._locale,
        )

    async def run_hsr(self, *, enka_hsr_down: bool) -> ProfileView:
        hoyolab_characters: list[HoyolabHSRCharacter] = []
        enka_data: enka.hsr.ShowcaseResponse | None = None
        hoyolab_user: StarRailUserStats | None = None
        builds = None

        async with enka.HSRClient(cache=self._enka_cache, use_enka_icons=False) as client:
            enka_data, builds = await self.fetch_enka_data(
                client, self._uid, enka_hsr_down=enka_hsr_down
            )

        if self._account is not None:
            client = self._account.client
            client.set_lang(self._locale)

            try:
                if enka_data is None:
                    hoyolab_user = await client.get_starrail_user()
                hoyolab_characters = await client.get_hoyolab_hsr_characters()
            except GenshinException:
                if enka_data is None:
                    # enka and hoyolab both failed, raise error
                    raise

        return ProfileView(
            self._uid,
            self._game,
            CARD_DATA.hsr,
            character_ids=self._character_ids,
            hoyolab_hsr_characters=hoyolab_characters,
            hoyolab_hsr_user=hoyolab_user,
            starrail_data=enka_data,
            account=self._account,
            builds=builds,
            owner=enka_data.owner if enka_data is not None else None,
            author=self._user,
            locale=self._locale,
        )

    async def run_zzz(self) -> ProfileView:
        enka_data: enka.zzz.ShowcaseResponse | None = None
        hoyolab_chars: Sequence[ZZZPartialAgent] | None = None
        zzz_user: RecordCard | None = None
        builds = None

        async with enka.ZZZClient(cache=self._enka_cache) as client:
            enka_data, builds = await self.fetch_enka_data(client, self._uid)

        if self._account is not None:
            client = self._account.client
            client.set_lang(self._locale)

            try:
                if enka_data is None:
                    record_cards = await client.get_record_cards()
                    zzz_user = next(
                        (card for card in record_cards if card.uid == self._account.uid), None
                    )
                hoyolab_chars = await client.get_zzz_agents()
            except GenshinException:
                if enka_data is None:
                    # enka and hoyolab both failed, raise error
                    raise

        return ProfileView(
            self._uid,
            self._game,
            CARD_DATA.zzz,
            character_ids=self._character_ids,
            account=self._account,
            zzz_data=enka_data,
            hoyolab_zzz_characters=hoyolab_chars,
            hoyolab_zzz_user=zzz_user,
            author=self._user,
            locale=self._locale,
            builds=builds,
        )
