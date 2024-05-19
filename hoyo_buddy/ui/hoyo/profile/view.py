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
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import CardNotReadyError
from hoyo_buddy.models import DrawInput

from ....icons import get_game_icon
from ....models import HoyolabHSRCharacter
from ....utils import upload_image
from ...components import (
    Button,
    Select,
    View,
)
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import CharacterSelect
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

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator


Character: TypeAlias = HoyolabHSRCharacter | enka.gi.Character | enka.hsr.Character


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
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.hoyolab_characters = hoyolab_characters
        self.hoyolab_user = hoyolab_user
        self.starrail_data = starrail_data
        self.genshin_data = genshin_data
        self.live_data_character_ids = [k for k in cache_extras if cache_extras[k]["live"]]

        self.uid = uid
        self.game = game
        self.cache_extras = cache_extras
        self.character_id: str | None = None
        self.characters: Sequence[Character] = []

        self._card_settings: CardSettings | None = None
        self._card_data = card_data
        self._account = account
        self._hoyolab_over_enka = hoyolab_over_enka

    def _set_characters(self) -> None:
        """Set the characters list."""
        characters: Sequence[Character] = []

        if self.game is Game.STARRAIL:
            if self._hoyolab_over_enka and self.hoyolab_characters:
                self.characters = self.hoyolab_characters
                return

            enka_chara_ids: list[str] = []
            if self.starrail_data is not None:
                for chara in self.starrail_data.characters:
                    enka_chara_ids.append(str(chara.id))
                    characters.append(chara)
            for chara in self.hoyolab_characters:
                if str(chara.id) not in enka_chara_ids:
                    characters.append(chara)

        elif self.game is Game.GENSHIN:
            assert self.genshin_data is not None
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
                title=player.nickname,
                description=LocaleStr(
                    "Trailblaze Level: {level}\n"
                    "Equilibrium Level: {world_level}\n"
                    "Friend Count: {friend_count}\n"
                    "Light Cones: {light_cones}\n"
                    "Characters: {characters}\n"
                    "Achievements: {achievements}\n",
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
                title=player.nickname,
                description=LocaleStr(
                    "Adventure Rank: {adventure_rank}\n"
                    "Spiral Abyss: {spiral_abyss}\n"
                    "Achievements: {achievements}\n",
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
            # There is no hsr cache, mihomo isnt working, but hoyolab is working
            player = self.hoyolab_user.info
            stats = self.hoyolab_user.stats
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=player.nickname,
                description=LocaleStr(
                    "Trailblaze Level: {level}\n"
                    "Characters: {characters}\n"
                    "Chests: {chest}\n"
                    "Memory of Chaos: {moc}\n"
                    "Achievements: {achievements}\n",
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
                title=LocaleStr("No data available", key="profile.no_data.title"),
                description=LocaleStr(
                    "Game services are currently down; luckily, Hoyo Buddy helped you to cache your character data, so you can still view your character cards as normal.",
                    key="profile.no_data.description",
                ),
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
        if self._account is not None:
            self.add_item(RemoveFromCacheButton())
        self.add_item(CardInfoButton())
        if self.characters:
            self.add_item(CharacterSelect(self.characters, self.cache_extras))

    async def _draw_src_character_card(
        self,
        uid: int,
        character: enka.hsr.Character,
        template: str,
        session: aiohttp.ClientSession,
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        template_num = int(template[-1])
        payload = {
            "uid": uid,
            "lang": LOCALE_TO_HSR_CARD_API_LANG.get(
                Locale(self.cache_extras[str(character.id)]["locale"]),
                "en",
            ),
            "template": template_num,
            "character_id": str(character.id),
            "character_art": self._card_settings.current_image,
            "color": self._card_settings.custom_primary_color,
        }
        endpoint = "http://localhost:7652/star-rail-card"

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_enka_card(
        self,
        uid: int,
        character: enka.gi.Character,
        session: aiohttp.ClientSession,
        template: str,
    ) -> BytesIO:
        """Draw GI character card in EnkaCard2, ENCard, enka-card templates."""
        assert self._card_settings is not None

        payload = {
            "uid": uid,
            "lang": LOCALE_TO_GI_CARD_API_LANG[
                Locale(self.cache_extras[str(character.id)]["locale"])
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
            payload["color"] = self._card_settings.custom_primary_color
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
        character: enka.hsr.Character | HoyolabHSRCharacter,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        character_data = self._card_data.get(str(character.id))
        if character_data is None:
            raise CardNotReadyError(character.name)

        default_art = f"https://raw.githubusercontent.com/FortOfFans/HSR/main/spriteoutput/avatardrawcardresult/{character.id}.png"
        art = self._card_settings.current_image or await upload_image(
            session, image_url=default_art
        )

        if self._card_settings.custom_primary_color is None:
            primary: str = character_data["primary"]
            if "primary-dark" in character_data and self._card_settings.dark_mode:
                primary: str = character_data["primary-dark"]
        else:
            primary = self._card_settings.custom_primary_color

        return await draw_hsr_build_card(
            DrawInput(
                dark_mode=self._card_settings.dark_mode,
                locale=Locale(self.cache_extras[str(character.id)]["locale"]),
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
        character: enka.gi.Character,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        if self._card_settings.current_image is not None:
            art = self._card_settings.current_image
        elif character.costume is not None:
            art = character.costume.icon.gacha
        else:
            art = character.icon.gacha

        return await draw_gi_build_card(
            DrawInput(
                dark_mode=self._card_settings.dark_mode,
                locale=Locale(self.cache_extras[str(character.id)]["locale"]),
                session=session,
                filename="card.webp",
                executor=executor,
                loop=loop,
            ),
            character,
            art,
            0.8 if self._card_settings.current_image is None else 1.0,
        )

    async def draw_card(self, i: INTERACTION) -> io.BytesIO:
        """Draw the character card and return the bytes object."""
        assert self.character_id is not None

        character = next(c for c in self.characters if str(c.id) == self.character_id)

        # Initialize card settings
        card_settings = await CardSettings.get_or_none(
            user_id=i.user.id, character_id=self.character_id
        )
        if card_settings is None:
            card_settings = await CardSettings.create(
                user_id=i.user.id, character_id=self.character_id, dark_mode=False
            )
        self._card_settings = card_settings

        # Force change the template to hb1 if is cached data or HoyolabHSRCharacter
        if not self.cache_extras[self.character_id]["live"] or isinstance(
            character, HoyolabHSRCharacter
        ):
            self._card_settings.template = "hb1"
            await self._card_settings.save(update_fields=("template",))

        template = self._card_settings.template
        bytes_obj = None

        try:
            if isinstance(character, enka.hsr.Character | HoyolabHSRCharacter):
                if "hb" in template or isinstance(character, HoyolabHSRCharacter):
                    bytes_obj = await self._draw_hb_hsr_character_card(
                        character, i.client.session, i.client.executor, i.client.loop
                    )
                elif isinstance(character, enka.hsr.Character):
                    bytes_obj = await self._draw_src_character_card(
                        self.uid, character, template, i.client.session
                    )
            elif isinstance(character, enka.gi.Character):
                if "hb" in template:
                    bytes_obj = await self._draw_hb_gi_character_card(
                        character, i.client.session, i.client.executor, i.client.loop
                    )
                else:
                    bytes_obj = await self._draw_enka_card(
                        self.uid, character, i.client.session, template
                    )
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
        i: INTERACTION,
        item: Select[ProfileView] | Button[ProfileView],
        *,
        unset_loading_state: bool = True,
    ) -> None:
        try:
            bytes_obj = await self.draw_card(i)
            bytes_obj.seek(0)
        except Exception:
            if unset_loading_state:
                await item.unset_loading_state(i)
            raise

        attachments = [File(bytes_obj, filename="card.webp")]

        if unset_loading_state:
            await item.unset_loading_state(i, attachments=attachments, embed=self.card_embed)
        else:
            await i.edit_original_response(attachments=attachments, embed=self.card_embed)

    async def start(self, i: INTERACTION) -> None:
        self._set_characters()
        self._add_items()
        await i.followup.send(embed=self.player_embed, view=self)
        self.message = await i.original_response()
