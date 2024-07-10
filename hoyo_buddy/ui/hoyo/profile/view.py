from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, TypeAlias

import enka
from discord import File, Locale

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.constants import LOCALE_TO_GI_CARD_API_LANG, LOCALE_TO_HSR_CARD_API_LANG
from hoyo_buddy.db.models import CardSettings, HoyoAccount
from hoyo_buddy.draw.main_funcs import draw_gi_build_card, draw_hsr_build_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import CharacterType, Game
from hoyo_buddy.exceptions import CardNotReadyError, DownloadImageFailedError
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.models import DrawInput, HoyolabHSRCharacter
from hoyo_buddy.ui import Button, Select, View

from .items.build_select import BuildSelect
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import CharacterSelect, determine_chara_type
from .items.player_btn import PlayerInfoButton
from .items.rmv_from_cache_btn import RemoveFromCacheButton

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    import io
    from collections.abc import Sequence

    import aiohttp
    from discord import Member, User
    from genshin.models import StarRailUserStats

    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.types import Builds, Interaction


Character: TypeAlias = HoyolabHSRCharacter | enka.gi.Character | enka.hsr.Character
GI_CARD_ENDPOINTS = {
    "hattvr": "http://localhost:7652/hattvr-enka-card",
    "encard": "http://localhost:7652/en-card",
    "enkacard": "http://localhost:7652/enka-card",
}


class ProfileView(View):
    def __init__(
        self,
        uid: int,
        game: Game,
        cache_extras: dict[str, dict[str, Any]],
        card_data: dict[str, Any],
        *,
        hoyolab_characters: list[HoyolabHSRCharacter],
        hoyolab_user: StarRailUserStats | None = None,
        starrail_data: enka.hsr.ShowcaseResponse | None = None,
        genshin_data: enka.gi.ShowcaseResponse | None = None,
        account: HoyoAccount | None,
        hoyolab_over_enka: bool = False,
        builds: Builds | None = None,
        owner: enka.Owner | None = None,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.hoyolab_characters = hoyolab_characters
        self.hoyolab_user = hoyolab_user
        self.starrail_data = starrail_data
        self.genshin_data = genshin_data

        self.uid = uid
        self.game = game
        self.cache_extras = cache_extras
        self.character_id: str | None = None
        self.character_type: CharacterType | None = None
        self.characters: Sequence[Character] = []

        self._card_settings: CardSettings | None = None
        self._card_data = card_data
        self._account = account
        self._hoyolab_over_enka = hoyolab_over_enka
        self._builds = builds or {}

        self._owner_username: str | None = owner.username if owner is not None else None
        self._owner_hash: str | None = owner.hash if owner is not None else None
        self._build_id: int | None = None

    def _get_character(self, character_id: str) -> Character:
        return next(c for c in self.characters if str(c.id) == character_id)

    def _set_characters(self) -> None:  # noqa: PLR0912
        """Set the characters list."""
        characters: Sequence[Character] = []

        if self.game is Game.STARRAIL:
            if self._hoyolab_over_enka and self.hoyolab_characters:
                self.characters = self.hoyolab_characters
                return

            enka_chara_ids: list[str] = []
            if self.starrail_data is not None:
                for chara in self.starrail_data.characters:
                    chara_type = determine_chara_type(
                        str(chara.id), self.cache_extras, self._builds, False
                    )
                    if chara_type is CharacterType.CACHE:
                        continue
                    enka_chara_ids.append(str(chara.id))
                    characters.append(chara)

            for chara in self.hoyolab_characters:
                if str(chara.id) not in enka_chara_ids:
                    enka_chara_ids.append(str(chara.id))
                    characters.append(chara)

            if self._builds:
                for builds in self._builds.values():
                    character = builds[0].character
                    if str(character.id) not in enka_chara_ids:
                        characters.append(character)

        elif self.game is Game.GENSHIN:
            assert self.genshin_data is not None
            if self._builds:
                for builds in self._builds.values():
                    character = builds[0].character
                    characters.append(character)
            else:
                characters.extend(self.genshin_data.characters)

        self.characters = characters

    @property
    def player_embed(self) -> DefaultEmbed:
        """Player info embed."""
        if self.starrail_data is not None:
            player = self.starrail_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=f"{player.nickname} ({self.uid})",
                description=LocaleStr(
                    key="profile.player_info.embed.description",
                    level=player.level,
                    world_level=player.equilibrium_level,
                    friend_count=player.friend_count,
                    light_cones=player.stats.light_cone_count,
                    characters=player.stats.character_count,
                    achievements=player.stats.achievement_count,
                ),
            )
            embed.set_thumbnail(url=player.icon)
            if player.signature:
                embed.set_footer(text=player.signature)
        elif self.genshin_data is not None:
            player = self.genshin_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=f"{player.nickname} ({self.uid})",
                description=LocaleStr(
                    key="profile.player_info.gi.embed.description",
                    adventure_rank=player.level,
                    spiral_abyss=f"{player.abyss_floor}-{player.abyss_level}",
                    achievements=player.achievements,
                ),
            )
            embed.set_thumbnail(url=player.profile_picture_icon.circle)
            embed.set_image(url=player.namecard.full)
            if player.signature:
                embed.set_footer(text=player.signature)
        elif self.hoyolab_user is not None:
            # There is no hsr cache, enka isnt working, but hoyolab is working
            player = self.hoyolab_user.info
            stats = self.hoyolab_user.stats
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=f"{player.nickname} ({self.uid})",
                description=LocaleStr(
                    key="profile.player_info.hoyolab.embed.description",
                    level=player.level,
                    characters=stats.avatar_num,
                    chest=stats.chest_num,
                    moc=stats.abyss_process,
                    achievements=stats.achievement_num,
                ),
            )
        else:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr(key="profile.no_data.title"),
                description=LocaleStr(key="profile.no_data.description"),
            )

        return embed

    @property
    def card_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator)
        embed.set_image(url="attachment://card.webp")
        if self._account is not None:
            embed.add_acc_info(self._account)
        else:
            embed.set_author(name=f"UID: {self.uid}", icon_url=get_game_icon(self.game))
        return embed

    def _add_items(self) -> None:
        self.add_item(PlayerInfoButton())
        self.add_item(CardSettingsButton())
        self.add_item(CardInfoButton())

        if self._account is not None:
            self.add_item(RemoveFromCacheButton())
        if self.characters:
            self.add_item(CharacterSelect(self.characters, self.cache_extras, self._builds))
        self.add_item(BuildSelect())

    async def _draw_src_character_card(
        self, session: aiohttp.ClientSession, character: Character
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        cache_extra = self.cache_extras.get(str(character.id))
        locale = self.locale if cache_extra is None else Locale(cache_extra["locale"])

        template = self._card_settings.template
        payload = {
            "uid": self.uid,
            "lang": LOCALE_TO_HSR_CARD_API_LANG.get(locale, "en"),
            "template": int(template[-1]),
            "character_id": str(character.id),
            "character_art": self._card_settings.current_image,
            "color": self._card_settings.custom_primary_color,
        }
        if all(v is not None for v in (self._owner_hash, self._owner_username, self._build_id)):
            payload["owner"] = {
                "username": self._owner_username,
                "hash": self._owner_hash,
                "build_id": self._build_id,
            }

        if isinstance(character, HoyolabHSRCharacter):
            assert self._account is not None
            payload["cookies"] = self._account.cookies

        endpoint = "http://localhost:7652/star-rail-card"

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            if resp.status != 200:
                raise ValueError(await resp.text())
            return BytesIO(await resp.read())

    async def _draw_enka_card(
        self, session: aiohttp.ClientSession, character: Character
    ) -> BytesIO:
        """Draw GI character card in EnkaCard2, ENCard, enka-card templates."""
        assert self._card_settings is not None

        cache_extra = self.cache_extras.get(str(character.id))
        locale = self.locale if cache_extra is None else Locale(cache_extra["locale"])
        template = self._card_settings.template

        payload = {
            "uid": self.uid,
            "lang": LOCALE_TO_GI_CARD_API_LANG.get(locale, "en"),
            "character_id": str(character.id),
            "character_art": self._card_settings.current_image,
            "color": self._card_settings.custom_primary_color,
            "template": int(template[-1]),
        }
        if all(v is not None for v in (self._owner_hash, self._owner_username, self._build_id)):
            payload["owner"] = {
                "username": self._owner_username,
                "hash": self._owner_hash,
                "build_id": self._build_id,
            }

        endpoint = GI_CARD_ENDPOINTS.get(template[:-1])
        if endpoint is None:
            msg = f"Invalid template: {template}"
            raise ValueError(msg)

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            if resp.status != 200:
                raise ValueError(await resp.text())
            return BytesIO(await resp.read())

    async def _draw_hb_hsr_character_card(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
        character: Character,
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        assert isinstance(character, enka.hsr.Character | HoyolabHSRCharacter)
        character_data = self._card_data.get(str(character.id))
        if character_data is None:
            raise CardNotReadyError(character.name)

        default_art = f"https://raw.githubusercontent.com/FortOfFans/HSR/main/spriteoutput/avatardrawcardresult/{character.id}.png"
        art = self._card_settings.current_image or default_art

        if self._card_settings.custom_primary_color is None:
            primary: str = character_data["primary"]
            if "primary-dark" in character_data and self._card_settings.dark_mode:
                primary: str = character_data["primary-dark"]
        else:
            primary = self._card_settings.custom_primary_color

        cache_extra = self.cache_extras.get(str(character.id))
        locale = self.locale if cache_extra is None else Locale(cache_extra["locale"])

        return await draw_hsr_build_card(
            DrawInput(
                dark_mode=self._card_settings.dark_mode,
                locale=locale,
                session=session,
                filename="card.webp",
                executor=executor,
                loop=loop,
            ),
            character,
            art,
            primary,
        )

    async def _draw_hb_gi_character_card(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
        character: Character,
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        assert isinstance(character, enka.gi.Character)

        if self._card_settings.current_image is not None:
            art = self._card_settings.current_image
        elif character.costume is not None:
            art = character.costume.icon.gacha
        else:
            art = character.icon.gacha

        cache_extra = self.cache_extras.get(str(character.id))
        locale = self.locale if cache_extra is None else Locale(cache_extra["locale"])

        return await draw_gi_build_card(
            DrawInput(
                dark_mode=self._card_settings.dark_mode,
                locale=locale,
                session=session,
                filename="card.webp",
                executor=executor,
                loop=loop,
            ),
            character,
            art,
            0.8 if self._card_settings.current_image is None else 1.0,
        )

    async def draw_card(self, i: Interaction, *, character: Character | None = None) -> io.BytesIO:
        """Draw the character card and return the bytes object."""
        assert self.character_id is not None

        character = character or self._get_character(self.character_id)

        # Initialize card settings
        card_settings = await CardSettings.get_or_none(
            user_id=i.user.id, character_id=self.character_id
        )
        if card_settings is None:
            card_settings = await CardSettings.create(
                user_id=i.user.id, character_id=self.character_id, dark_mode=False
            )
        self._card_settings = card_settings

        # Force change the template to hb1 if is cached data
        if self.character_type is CharacterType.CACHE:
            self._card_settings.template = "hb1"
            await self._card_settings.save(update_fields=("template",))

        template = self._card_settings.template
        bytes_obj = None

        try:
            if self.game is Game.STARRAIL:
                if "hb" in template:
                    bytes_obj = await self._draw_hb_hsr_character_card(
                        i.client.session, i.client.executor, i.client.loop, character
                    )
                else:
                    bytes_obj = await self._draw_src_character_card(i.client.session, character)
            elif self.game is Game.GENSHIN:
                if "hb" in template:
                    bytes_obj = await self._draw_hb_gi_character_card(
                        i.client.session, i.client.executor, i.client.loop, character
                    )
                else:
                    bytes_obj = await self._draw_enka_card(i.client.session, character)
        except Exception:
            # Reset the template to hb1 if an error occurs
            self._card_settings.template = "hb1"
            await self._card_settings.save(update_fields=("template",))
            raise

        # This should never happen, this is just to address variable unbound error for bytes_obj
        if bytes_obj is None:
            msg = "Failed to draw the character card."
            raise RuntimeError(msg)

        return bytes_obj

    async def update(
        self,
        i: Interaction,
        item: Select[ProfileView] | Button[ProfileView],
        *,
        unset_loading_state: bool = True,
        character: Character | None = None,
    ) -> None:
        try:
            bytes_obj = await self.draw_card(i, character=character)
            bytes_obj.seek(0)
        except Exception as e:
            if isinstance(e, DownloadImageFailedError):
                assert self._card_settings is not None
                self._card_settings.current_image = None
                await self._card_settings.save(update_fields=("current_image",))
            if unset_loading_state:
                await item.unset_loading_state(i)
            raise ThirdPartyCardTempError from e

        attachments = [File(bytes_obj, filename="card.webp")]

        if unset_loading_state:
            await item.unset_loading_state(i, attachments=attachments, embed=self.card_embed)
        else:
            await i.edit_original_response(attachments=attachments, embed=self.card_embed)

    async def start(self, i: Interaction) -> None:
        self._set_characters()
        self._add_items()
        await i.followup.send(embed=self.player_embed, view=self)
        self.message = await i.original_response()
