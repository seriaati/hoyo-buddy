from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from genshin import GenshinException
from seria.utils import read_yaml

from ..db.models import EnkaCache, HoyoAccount
from ..hoyo.clients.enka.gi import EnkaGIClient
from ..hoyo.clients.enka.hsr import EnkaHSRClient
from ..ui.hoyo.profile.view import ProfileView

if TYPE_CHECKING:
    import discord

    from ..bot.translator import Translator
    from ..enums import Game
    from ..models import HoyolabHSRCharacter


class ProfileCommand:
    def __init__(
        self,
        *,
        uid: int,
        game: Game,
        account: HoyoAccount | None,
        locale: discord.Locale,
        user: discord.User | discord.Member,
        translator: Translator,
    ) -> None:
        self._uid = uid
        self._game = game
        self._account = account
        self._locale = locale
        self._user = user
        self._translator = translator

    async def run_genshin(self) -> ProfileView:
        client = EnkaGIClient(locale=self._locale)
        genshin_data, _ = await client.fetch_showcase(self._uid)

        builds = None
        if genshin_data is not None and genshin_data.owner is not None:
            builds = await client.fetch_builds(genshin_data.owner)

        cache = await EnkaCache.get(uid=self._uid)
        return ProfileView(
            self._uid,
            self._game,
            cache.extras,
            await read_yaml("hoyo-buddy-assets/assets/gi-build-card/data.yaml"),
            hoyolab_characters=[],
            genshin_data=genshin_data,
            account=self._account,
            builds=builds,
            owner=genshin_data.owner,
            author=self._user,
            locale=self._locale,
            translator=self._translator,
        )

    async def run_hsr(self) -> ProfileView:
        hoyolab_charas: list[HoyolabHSRCharacter] = []
        starrail_data: enka.hsr.ShowcaseResponse | None = None
        hoyolab_user = None
        errored = False
        builds = None

        client = EnkaHSRClient(self._locale)

        try:
            starrail_data, errored = await client.fetch_showcase(self._uid)
        except enka.errors.GameMaintenanceError:
            if self._account is None:
                # enka fails and no hoyolab account provided, raise error
                raise

        if starrail_data is not None and starrail_data.owner is not None:
            builds = await client.fetch_builds(starrail_data.owner)

        if self._account is not None:
            client = self._account.client
            client.set_lang(self._locale)
            try:
                if starrail_data is None:
                    hoyolab_user = await client.get_starrail_user()
                hoyolab_charas = await client.get_hoyolab_hsr_characters()
            except GenshinException:
                if starrail_data is None:
                    # enka and hoyolab both failed, raise error
                    raise

        cache = await EnkaCache.get(uid=self._uid)
        return ProfileView(
            self._uid,
            self._game,
            cache.extras,
            await read_yaml("hoyo-buddy-assets/assets/hsr-build-card/data.yaml"),
            hoyolab_characters=hoyolab_charas,
            hoyolab_user=hoyolab_user,
            starrail_data=starrail_data,
            account=self._account,
            hoyolab_over_enka=errored,
            builds=builds,
            owner=starrail_data.owner if starrail_data is not None else None,
            author=self._user,
            locale=self._locale,
            translator=self._translator,
        )
