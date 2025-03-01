from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from genshin import GenshinException

from hoyo_buddy.db import EnkaCache, HoyoAccount
from hoyo_buddy.draw.card_data import CARD_DATA

from ..exceptions import InvalidQueryError
from ..hoyo.clients.enka.gi import EnkaGIClient
from ..hoyo.clients.enka.hsr import EnkaHSRClient
from ..ui.hoyo.profile.view import ProfileView

if TYPE_CHECKING:
    import discord
    from genshin.models import GenshinUserStats, StarRailUserStats

    from hoyo_buddy.models import HoyolabGICharacter

    from ..enums import Game
    from ..models import HoyolabHSRCharacter


class ProfileCommand:
    def __init__(
        self,
        *,
        uid: int,
        game: Game,
        account: HoyoAccount | None,
        character_ids: list[str | None],
        locale: discord.Locale,
        user: discord.User | discord.Member,
    ) -> None:
        self._uid = uid
        self._game = game
        self._account = account
        self._character_ids = list({id_ for id_ in character_ids if id_ is not None})
        self._locale = locale
        self._user = user

    async def run_genshin(self) -> ProfileView:
        hoyolab_characters: list[HoyolabGICharacter] = []
        enka_data: enka.gi.ShowcaseResponse | None = None
        hoyolab_user: GenshinUserStats | None = None
        errored = False
        builds = None

        client = EnkaGIClient(self._locale)

        try:
            enka_data, errored = await client.fetch_showcase(self._uid)
        except enka.errors.EnkaAPIError:
            if self._account is None:
                # enka fails and no hoyolab account provided, raise error
                raise

        if enka_data is not None and enka_data.owner is not None:
            builds = await client.fetch_builds(enka_data.owner)

        if self._account is not None:
            client = self._account.client
            client.set_lang(self._locale)
            try:
                if enka_data is None:
                    hoyolab_user = await client.get_genshin_user(self._uid)
                hoyolab_characters = await client.get_hoyolab_gi_characters()
            except GenshinException:
                if enka_data is None:
                    # enka and hoyolab both failed, raise error
                    raise

        cache = await EnkaCache.get(uid=self._uid)
        return ProfileView(
            self._uid,
            self._game,
            cache.extras,
            CARD_DATA.gi,
            character_ids=self._character_ids,
            hoyolab_gi_characters=hoyolab_characters,
            hoyolab_gi_user=hoyolab_user,
            hoyolab_over_enka=errored,
            genshin_data=enka_data,
            account=self._account,
            builds=builds,
            owner=enka_data.owner if enka_data is not None else None,
            author=self._user,
            locale=self._locale,
        )

    async def run_hsr(self) -> ProfileView:
        hoyolab_characters: list[HoyolabHSRCharacter] = []
        enka_data: enka.hsr.ShowcaseResponse | None = None
        hoyolab_user: StarRailUserStats | None = None
        errored = False
        builds = None

        client = EnkaHSRClient(self._locale)

        try:
            enka_data, errored = await client.fetch_showcase(self._uid)
        except enka.errors.EnkaAPIError:
            if self._account is None:
                # enka fails and no hoyolab account provided, raise error
                raise

        if enka_data is not None and enka_data.owner is not None:
            builds = await client.fetch_builds(enka_data.owner)

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

        cache = await EnkaCache.get(uid=self._uid)
        return ProfileView(
            self._uid,
            self._game,
            cache.extras,
            CARD_DATA.hsr,
            character_ids=self._character_ids,
            hoyolab_hsr_characters=hoyolab_characters,
            hoyolab_hsr_user=hoyolab_user,
            starrail_data=enka_data,
            account=self._account,
            hoyolab_over_enka=errored,
            builds=builds,
            owner=enka_data.owner if enka_data is not None else None,
            author=self._user,
            locale=self._locale,
        )

    async def run_zzz(self) -> ProfileView:
        if self._account is None:
            raise InvalidQueryError

        client = self._account.client
        client.set_lang(self._locale)
        zzz_data = await client.get_zzz_agents()
        record_cards = await client.get_record_cards()
        zzz_user = next((card for card in record_cards if card.uid == self._account.uid), None)
        cache, _ = await EnkaCache.get_or_create(uid=self._uid)
        return ProfileView(
            self._uid,
            self._game,
            cache.extras,
            CARD_DATA.zzz,
            character_ids=self._character_ids,
            account=self._account,
            zzz_data=zzz_data,
            zzz_user=zzz_user,
            author=self._user,
            locale=self._locale,
        )
