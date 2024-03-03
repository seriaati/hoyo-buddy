import asyncio
from io import BytesIO
from typing import TYPE_CHECKING, Any

from discord.utils import get as dget
from enka import Language as EnkaLang
from mihomo.models import Character as HSRCharacter

from ....bot.translator import LocaleStr
from ....constants import ENKA_LANG_TO_CARD_API_LANG, ENKA_LANG_TO_LOCALE, MIHOMO_LANG_TO_LOCALE
from ....db.models import CardSettings
from ....draw.hoyo.genshin.build_card import draw_genshin_card
from ....draw.hoyo.hsr.build_card import draw_build_card
from ....draw.static import download_and_save_static_images
from ....embeds import DefaultEmbed
from ....enums import Game
from ....exceptions import CardNotReadyError
from ...components import (
    View,
)
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import CharacterSelect
from .items.player_btn import PlayerButton
from .items.rmv_from_cache_btn import RemoveFromCacheButton

if TYPE_CHECKING:
    import io

    import aiohttp
    from discord import Locale, Member, User
    from enka.models import Character as GICharacter
    from enka.models import ShowcaseResponse
    from mihomo.models import StarrailInfoParsed

    from hoyo_buddy.bot.translator import Translator

    from ....bot.bot import INTERACTION


class ProfileView(View):
    def __init__(
        self,
        uid: int,
        game: "Game",
        cache_extras: dict[str, dict[str, Any]],
        card_data: dict[str, Any],
        star_rail_data: "StarrailInfoParsed" = None,  # type: ignore
        genshin_data: "ShowcaseResponse" = None,  # type: ignore
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.star_rail_data = star_rail_data
        self.genshin_data = genshin_data

        # Determine live data character IDs based on the game
        if game is Game.STARRAIL:
            self.live_data_character_ids = [
                char.id for char in star_rail_data.characters if cache_extras[char.id]["live"]
            ]
        else:
            self.live_data_character_ids = [
                str(char.id)
                for char in genshin_data.characters
                if cache_extras[str(char.id)]["live"]
            ]

        self.uid = uid
        self.game = game
        self.cache_extras = cache_extras
        self.character_id: str | None = None

        self._card_settings: CardSettings | None = None
        self._card_data = card_data

    @property
    def player_embed(self) -> DefaultEmbed:
        """Player info embed"""
        if self.game is Game.STARRAIL:
            player = self.star_rail_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=player.name,
                description=LocaleStr(
                    "Trailblaze Level: {level}\n"
                    "Equilibrium Level: {world_level}\n"
                    "Friend Count: {friend_count}\n"
                    "Light Cones: {light_cones}\n"
                    "Characters: {characters}\n"
                    "Achievements: {achievements}\n",
                    key="profile.player_info.embed.description",
                    level=player.level,
                    world_level=player.world_level,
                    friend_count=player.friend_count,
                    light_cones=player.light_cones,
                    characters=player.characters,
                    achievements=player.achievements,
                ),
            )
            embed.set_thumbnail(url=player.avatar.icon)
            if player.signature:
                embed.set_footer(text=player.signature)
        else:
            player = self.genshin_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=player.nickname,
                description=LocaleStr(
                    "Adventure Rank: {adventure_rank}\n"
                    "Characters: {characters}\n"
                    "Spiral Abyss: {spiral_abyss}\n"
                    "Achievements: {achievements}\n",
                    key="profile.player_info.embed.description",
                    adventure_rank=player.level,
                    characters=len(player.showcase_characters),
                    spiral_abyss=f"{player.abyss_level}-{player.abyss_floor}",
                    achievements=player.achievements,
                ),
            )
            embed.set_thumbnail(url=player.profile_picture_icon.circle)
            embed.set_image(url=player.namecard.full)
            if player.signature:
                embed.set_footer(text=player.signature)

        return embed

    def _add_items(self) -> None:
        self.add_item(PlayerButton())
        self.add_item(CardSettingsButton())
        self.add_item(RemoveFromCacheButton())
        self.add_item(CardInfoButton())
        self.add_item(
            CharacterSelect(
                self.star_rail_data.characters
                if self.game is Game.STARRAIL
                else self.genshin_data.characters,
                self.cache_extras,
            )
        )

    async def _draw_src_character_card(
        self,
        uid: int,
        character: "HSRCharacter",
        template: str,
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        template_num = int(template[-1])
        payload = {
            "uid": uid,
            "lang": self.cache_extras[character.id]["lang"],
            "template": template_num,
            "character_name": character.name,
            "character_art": self._card_settings.current_image,
        }
        endpoint = "http://localhost:7652/star-rail-card"

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_enka_card(
        self,
        uid: int,
        character: "GICharacter",
        session: "aiohttp.ClientSession",
        template: str,
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        payload = {
            "uid": uid,
            "lang": ENKA_LANG_TO_CARD_API_LANG[
                EnkaLang(self.cache_extras[str(character.id)]["lang"])
            ],
            "character_id": str(character.id),
            "character_art": self._card_settings.current_image,
        }
        if template == "hattvr1":
            del payload["character_art"]
            endpoint = "http://localhost:7652/hattvr-enka-card"
        elif "enkacard" in template:
            payload["template"] = int(template[-1])
            endpoint = "http://localhost:7652/enka-card"
        elif template == "encard1":
            del payload["character_id"]
            payload["character_name"] = character.name
            endpoint = "http://localhost:7652/en-card"
        else:
            msg = f"Invalid template: {template}"
            raise NotImplementedError(msg)

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_hb_hsr_character_card(
        self,
        character: "HSRCharacter",
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        character_data = self._card_data.get(character.id)
        if character_data is None:
            raise CardNotReadyError(character.name)

        art = self._card_settings.current_image or character_data["arts"][0]

        urls = await self._retrieve_hsr_image_urls(character, art)
        await download_and_save_static_images(list(urls), "hsr-build-card", session)

        if self._card_settings.custom_primary_color is None:
            primary = character_data["primary"]
            if "primary-dark" in character_data and self._card_settings.dark_mode:
                primary = character_data["primary-dark"]
            self._card_settings.custom_primary_color = primary

        return await asyncio.to_thread(
            draw_build_card,
            character,
            MIHOMO_LANG_TO_LOCALE[self.cache_extras[character.id]["lang"]],
            self._card_settings.dark_mode,
            art,
            self._card_settings.custom_primary_color,
        )

    async def _draw_hb_gi_character_card(
        self,
        character: "GICharacter",
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        character_data = self._card_data.get(str(character.id))
        if character_data is None:
            raise CardNotReadyError(character.name)

        art = self._card_settings.current_image or character_data["arts"][0]

        urls = await self._retrieve_genshin_image_urls(character, art)
        await download_and_save_static_images(list(urls), "gi-build-card", session)

        return await asyncio.to_thread(
            draw_genshin_card,
            ENKA_LANG_TO_LOCALE[EnkaLang(self.cache_extras[str(character.id)]["lang"])],
            self._card_settings.dark_mode,
            character,
            art,
        )

    async def _retrieve_hsr_image_urls(self, character: "HSRCharacter", art: str) -> set[str]:
        """Retrieve all image URLs needed to draw the HSR card."""
        urls: set[str] = set()
        urls.add(art)
        for trace in character.traces:
            urls.add(trace.icon)
        for trace in character.trace_tree:
            urls.add(trace.icon)
        for relic in character.relics:
            urls.add(relic.icon)
            urls.add(relic.main_affix.icon)
            for affix in relic.sub_affixes:
                urls.add(affix.icon)
        for attr in character.attributes:
            urls.add(attr.icon)
        for addition in character.additions:
            urls.add(addition.icon)
        if character.light_cone is not None:
            urls.add(character.light_cone.portrait)
            for attr in character.light_cone.attributes:
                urls.add(attr.icon)
        urls.add(
            "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/property/IconEnergyRecovery.png"
        )

        return urls

    async def _retrieve_genshin_image_urls(self, character: "GICharacter", art: str) -> set[str]:
        urls: set[str] = set()
        urls.add(art)
        urls.add(character.weapon.icon)
        urls.add(character.icon.gacha)
        for artifact in character.artifacts:
            urls.add(artifact.icon)
        for talent in character.talents:
            urls.add(talent.icon)
        for constellation in character.constellations:
            urls.add(constellation.icon)

        return urls

    async def draw_card(self, i: "INTERACTION") -> "io.BytesIO":
        """Draw the character card and return the bytes object."""
        assert self.character_id is not None

        if self.game is Game.STARRAIL:
            character = dget(self.star_rail_data.characters, id=self.character_id)
        else:
            character = dget(self.genshin_data.characters, id=int(self.character_id))

        if character is None:
            msg = f"Character not found: {self.character_id}"
            raise ValueError(msg)

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
        if (
            not self.cache_extras[self.character_id]["live"]
            and "hb" not in self._card_settings.template
        ):
            self._card_settings.template = "hb1"
            await self._card_settings.save()

        template = self._card_settings.template

        if isinstance(character, HSRCharacter):
            if "hb" in template:
                bytes_obj = await self._draw_hb_hsr_character_card(character, i.client.session)
            else:
                bytes_obj = await self._draw_src_character_card(
                    self.uid, character, template, i.client.session
                )
        elif "hb" in template:
            bytes_obj = await self._draw_hb_gi_character_card(character, i.client.session)
        else:
            bytes_obj = await self._draw_enka_card(self.uid, character, i.client.session, template)

        return bytes_obj

    async def start(self, i: "INTERACTION") -> None:
        self._add_items()
        await i.followup.send(embed=self.player_embed, view=self)
        self.message = await i.original_response()
