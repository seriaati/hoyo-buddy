from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import akasha
import enka
from discord import File, Locale
from genshin.models import ZZZPartialAgent
from loguru import logger
from seria.utils import read_yaml

from hoyo_buddy.constants import (
    LOCALE_TO_GI_CARD_API_LANG,
    LOCALE_TO_HSR_CARD_API_LANG,
    ZZZ_AGENT_STAT_TO_DISC_SUBSTAT,
    ZZZ_AVATAR_BATTLE_TEMP_JSON,
    ZZZ_DISC_SUBSTATS,
)
from hoyo_buddy.db import EnkaCache, JSONFile, Settings, draw_locale, get_dyk, show_dismissible
from hoyo_buddy.draw.main_funcs import (
    draw_gi_build_card,
    draw_gi_team_card,
    draw_hsr_build_card,
    draw_hsr_team_card,
    draw_zzz_build_card,
    draw_zzz_team_card,
)
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import CharacterType, Game, Platform
from hoyo_buddy.exceptions import (
    CardNotReadyError,
    DownloadImageFailedError,
    FeatureNotImplementedError,
    ThirdPartyCardTempError,
)
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.models import Dismissible, DrawInput, HoyolabGICharacter, HoyolabHSRCharacter
from hoyo_buddy.ui import Button, Select, View
from hoyo_buddy.ui.hoyo.profile.items.image_settings_btn import ImageSettingsButton
from hoyo_buddy.ui.hoyo.profile.items.team_card_settings_btn import TeamCardSettingsButton
from hoyo_buddy.ui.hoyo.profile.templates import TEMPLATES
from hoyo_buddy.utils import blur_uid, format_float, human_format_number

from .card_settings import get_card_settings
from .image_settings import get_default_art, get_default_collection, get_team_image
from .items.build_select import BuildSelect
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import MAX_VALUES, CharacterSelect, determine_chara_type
from .items.player_btn import PlayerInfoButton
from .items.redraw_card_btn import RedrawCardButton
from .items.rmv_from_cache_btn import RemoveFromCacheButton

if TYPE_CHECKING:
    import io
    from collections.abc import Sequence

    import aiohttp
    from discord import Member, User
    from genshin.models import GenshinUserStats, RecordCard, StarRailUserStats

    from hoyo_buddy.db import CardSettings, HoyoAccount
    from hoyo_buddy.types import Builds, Interaction


Character: TypeAlias = (
    HoyolabHSRCharacter
    | enka.gi.Character
    | enka.hsr.Character
    | ZZZPartialAgent
    | HoyolabGICharacter
)
HoyolabCharacter: TypeAlias = HoyolabHSRCharacter | HoyolabGICharacter | ZZZPartialAgent
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
        character_ids: list[str],
        hoyolab_hsr_characters: list[HoyolabHSRCharacter] | None = None,
        hoyolab_hsr_user: StarRailUserStats | None = None,
        hoyolab_gi_characters: list[HoyolabGICharacter] | None = None,
        hoyolab_gi_user: GenshinUserStats | None = None,
        starrail_data: enka.hsr.ShowcaseResponse | None = None,
        genshin_data: enka.gi.ShowcaseResponse | None = None,
        zzz_data: Sequence[ZZZPartialAgent] | None = None,
        zzz_user: RecordCard | None = None,
        account: HoyoAccount | None,
        hoyolab_over_enka: bool = False,
        builds: Builds | None = None,
        owner: enka.Owner | None = None,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self.hoyolab_hsr_characters = hoyolab_hsr_characters or []
        self.hoyolab_hsr_user = hoyolab_hsr_user
        self.hoyolab_gi_characters = hoyolab_gi_characters or []
        self.hoyolab_gi_user = hoyolab_gi_user

        self.starrail_data = starrail_data
        self.genshin_data = genshin_data
        self.zzz_data = zzz_data
        self.zzz_user = zzz_user

        self.uid = uid
        self.game = game
        self.cache_extras = cache_extras
        self.character_ids: list[str] = []
        self.character_type: CharacterType | None = None
        self.characters: dict[str, Character] = {}
        self._param_character_ids = character_ids

        self._card_data = card_data
        self._account = account
        self._hoyolab_over_enka = hoyolab_over_enka
        self._builds = builds or {}

        self._owner_username: str | None = owner.username if owner is not None else None
        self._owner_hash: str | None = owner.hash if owner is not None else None
        self._build_id: int | None = None

    async def fetch_cache_extras(self) -> dict[str, Any]:
        cache = await EnkaCache.get(uid=self.uid)
        self.cache_extras = cache.extras
        return cache.extras

    async def _fix_invalid_template(self, card_settings: CardSettings) -> None:
        if self.game not in TEMPLATES or card_settings.template not in TEMPLATES[self.game]:
            card_settings.template = "hb1"
            await card_settings.save(update_fields=("template",))

    async def _get_character_rank(
        self, character: Character, *, with_detail: bool = False
    ) -> str | None:
        async with akasha.AkashaAPI() as api:
            await api.refresh_user(self.uid)
            user_calcs = await api.get_calculations_for_user(self.uid)
            user_calc = next(
                (calc for calc in user_calcs if calc.character_id == character.id), None
            )
            if user_calc is None:
                return None

        if not user_calc.calculations:
            return None

        character_calc = user_calc.calculations[0]
        top_percent = LocaleStr(
            key="top_percent", percent=format_float(character_calc.top_percent)
        ).translate(self.locale)
        ranking = (
            f"{top_percent} ({character_calc.ranking}/{human_format_number(character_calc.out_of)})"
        )
        if not with_detail:
            return ranking
        variant_str = (
            f" {character_calc.variant.display_name if character_calc.variant is not None else ''}"
        )
        return f"{character_calc.short}{variant_str}\n{ranking}"

    def _check_card_data(self) -> None:
        for char_id in self.character_ids:
            if char_id not in self._card_data:
                raise CardNotReadyError(self.characters[char_id].name)

    def _set_characters_with_enka(self, game: Literal[Game.STARRAIL, Game.GENSHIN]) -> None:
        hoyolab_characters = (
            self.hoyolab_hsr_characters if game is Game.STARRAIL else self.hoyolab_gi_characters
        )
        data = self.starrail_data if game is Game.STARRAIL else self.genshin_data

        if self._hoyolab_over_enka and hoyolab_characters:
            self.characters = {str(chara.id): chara for chara in hoyolab_characters}
            return

        enka_chara_ids: list[str] = []
        if data is not None:
            for chara in data.characters:
                chara_type = determine_chara_type(
                    str(chara.id),
                    cache_extras=self.cache_extras,
                    builds=self._builds,
                    is_hoyolab=False,
                )
                if chara_type is CharacterType.CACHE:
                    continue
                enka_chara_ids.append(str(chara.id))
                self.characters[str(chara.id)] = chara

        for chara in hoyolab_characters:
            if str(chara.id) not in enka_chara_ids:
                enka_chara_ids.append(str(chara.id))
                self.characters[str(chara.id)] = chara

        for builds in self._builds.values():
            character = builds[0].character
            if str(character.id) not in enka_chara_ids:
                self.characters[str(character.id)] = character

    def _set_characters(self) -> None:
        if self.game is Game.STARRAIL:
            self._set_characters_with_enka(Game.STARRAIL)
        elif self.game is Game.GENSHIN:
            self._set_characters_with_enka(Game.GENSHIN)
        elif self.game is Game.ZZZ:
            assert self.zzz_data is not None
            for chara in self.zzz_data:
                self.characters[str(chara.id)] = chara

        for character_id in self._param_character_ids:
            if (
                len(self.character_ids) >= MAX_VALUES[self.game]
                or character_id not in self.characters
            ):
                break
            self.character_ids.append(character_id)

    @property
    def player_embed(self) -> DefaultEmbed:
        """Player info embed."""
        uid_str = blur_uid(self.uid) if self._account is not None else str(self.uid)
        if self.starrail_data is not None:
            player = self.starrail_data.player
            embed = DefaultEmbed(
                self.locale,
                title=f"{player.nickname} ({uid_str})",
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
                title=f"{player.nickname} ({uid_str})",
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
        elif self.hoyolab_hsr_user is not None:
            # There is no hsr cache, enka isnt working, but hoyolab is working
            player = self.hoyolab_hsr_user.info
            stats = self.hoyolab_hsr_user.stats
            embed = DefaultEmbed(
                self.locale,
                title=f"{player.nickname} ({uid_str})",
                description=LocaleStr(
                    key="profile.player_info.hoyolab.embed.description",
                    level=player.level,
                    characters=stats.avatar_num,
                    chest=stats.chest_num,
                    moc=stats.abyss_process,
                    achievements=stats.achievement_num,
                ),
            )
        elif self.zzz_user is not None:
            player = self.zzz_user
            data_str = "\n".join(f"{data.name}: {data.value}" for data in player.data)
            level_str = LevelStr(player.level).translate(self.locale)
            embed = DefaultEmbed(
                self.locale,
                title=f"{player.nickname} ({uid_str})",
                description=f"{level_str}\n{data_str}",
            )
        else:
            embed = DefaultEmbed(
                self.locale,
                title=LocaleStr(key="profile.no_data.title"),
                description=LocaleStr(key="profile.no_data.description"),
            )

        return embed

    @property
    def card_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale)
        embed.set_image(url="attachment://card.png")
        if self._account is not None:
            embed.add_acc_info(self._account)
        else:
            embed.set_author(name=f"UID: {self.uid}", icon_url=get_game_icon(self.game))
        return embed

    def _add_items(self) -> None:
        self.add_item(PlayerInfoButton(row=0))
        self.add_item(CardSettingsButton(row=0))
        self.add_item(TeamCardSettingsButton(row=1))
        self.add_item(ImageSettingsButton(row=1))
        self.add_item(RedrawCardButton(row=1))

        if self.characters:
            characters = [
                i[1]
                for i in sorted(
                    self.characters.items(), key=lambda x: (x[0] not in self.character_ids)
                )
            ]
            self.add_item(
                CharacterSelect(
                    self.game,
                    characters,
                    self.cache_extras,
                    self._builds,
                    self._account,
                    self.character_ids,
                    row=2,
                )
            )
        self.add_item(BuildSelect(row=3))

        if self._account is not None:
            self.add_item(RemoveFromCacheButton(row=4))
        self.add_item(CardInfoButton(row=4))

    async def _draw_src_character_card(
        self, session: aiohttp.ClientSession, character: Character, card_settings: CardSettings
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        template = card_settings.template
        payload = {
            "uid": self.uid,
            "lang": LOCALE_TO_HSR_CARD_API_LANG.get(
                await self.get_character_locale(character), "en"
            ),
            "template": int(template[-1]),
            "character_id": str(character.id),
            "character_art": card_settings.current_image,
            "color": card_settings.custom_primary_color,
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
            # API returns a png image
            if resp.status != 200:
                raise ValueError(await resp.text())
            return BytesIO(await resp.read())

    async def _draw_enka_card(
        self, session: aiohttp.ClientSession, character: Character, card_settings: CardSettings
    ) -> BytesIO:
        """Draw GI character card in EnkaCard2, ENCard, enka-card templates."""
        template = card_settings.template

        payload = {
            "uid": self.uid,
            "lang": LOCALE_TO_GI_CARD_API_LANG.get(
                await self.get_character_locale(character), "en"
            ),
            "character_id": str(character.id),
            "character_art": card_settings.current_image,
            "color": card_settings.custom_primary_color,
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
            # API returns a png image
            if resp.status != 200:
                raise ValueError(await resp.text())
            return BytesIO(await resp.read())

    async def _draw_hb_hsr_character_card(
        self, character: Character, card_settings: CardSettings, draw_input: DrawInput
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert isinstance(character, enka.hsr.Character | HoyolabHSRCharacter)

        character_id = str(character.id)
        character_data = self._card_data.get(character_id)
        if character_data is None:
            raise CardNotReadyError(character.name)

        image_url = card_settings.current_image or get_default_art(
            character, is_team=False, use_m3_art=card_settings.use_m3_art
        )

        if card_settings.custom_primary_color is None:
            primary: str = character_data["primary"]
            if "primary-dark" in character_data and card_settings.dark_mode:
                primary: str = character_data["primary-dark"]
        else:
            primary = card_settings.custom_primary_color

        template_num: Literal[1, 2] = int(card_settings.template[-1])  # pyright: ignore[reportAssignmentType]

        return await draw_hsr_build_card(
            draw_input, character, image_url, primary, template=template_num
        )

    async def _draw_hb_gi_character_card(
        self, character: Character, card_settings: CardSettings, draw_input: DrawInput
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert isinstance(character, enka.gi.Character | HoyolabGICharacter)

        image_url = card_settings.current_image or get_default_art(
            character, is_team=False, use_m3_art=card_settings.use_m3_art
        )

        template_num: Literal[1, 2] = int(card_settings.template[-1])  # pyright: ignore[reportAssignmentType]
        if template_num == 2:
            zoom = 0.7 if card_settings.current_image is None else 1.0
        else:
            zoom = 0.8 if card_settings.current_image is None else 1.0

        rank = None
        if card_settings.show_rank:
            try:
                rank = await self._get_character_rank(character, with_detail=template_num == 1)
            except (akasha.AkashaAPIError, TimeoutError):
                rank = None
            except Exception:
                logger.exception("Failed to fetch character rank from Akasha API")

        return await draw_gi_build_card(
            draw_input,
            character,
            image_url=image_url,
            zoom=zoom,
            template=template_num,
            top_crop=template_num == 2
            and card_settings.current_image
            in get_default_collection(str(character.id), self._card_data, game=Game.GENSHIN),
            rank=rank,
        )

    async def _draw_hb_zzz_character_card(
        self, character: Character, card_settings: CardSettings, draw_input: DrawInput
    ) -> BytesIO:
        """Draw ZZZ build card in Hoyo Buddy template."""
        assert isinstance(character, ZZZPartialAgent)
        assert self._account is not None

        # NOTE: This line is for testing new characters' templates
        character_id = character.id

        client = self._account.client
        client.set_lang(self.locale)
        agent = await client.get_zzz_agent_info(character.id)

        template_num: Literal[1, 2, 3, 4] = int(card_settings.template[-1])  # pyright: ignore[reportAssignmentType]
        if template_num == 2:
            temp2_card_data = await read_yaml(
                "hoyo-buddy-assets/assets/zzz-build-card/agent_data_temp2.yaml"
            )
            agent_temp1_data = self._card_data.get(str(character_id))
            agent_temp2_data = temp2_card_data.get(str(character_id))
            if agent_temp1_data is None or agent_temp2_data is None:
                raise CardNotReadyError(character.name)
            agent_temp2_data["color"] = agent_temp1_data["color"]
            agent_temp_data = agent_temp2_data
        else:
            # 1, 3, 4
            agent_temp_data = self._card_data.get(str(character_id))

        if agent_temp_data is None:
            raise CardNotReadyError(character.name)

        agent_special_stat_map: dict[str, list[int]] = await JSONFile.read(
            ZZZ_AVATAR_BATTLE_TEMP_JSON
        )

        return await draw_zzz_build_card(
            draw_input,
            agent,
            card_data=agent_temp_data,
            custom_color=card_settings.custom_primary_color,
            custom_image=card_settings.current_image,
            template=template_num,
            show_substat_rolls=card_settings.show_substat_rolls,
            agent_special_stat_map=agent_special_stat_map,
            hl_special_stats=card_settings.highlight_special_stats,
            hl_substats=card_settings.highlight_substats,
            use_m3_art=card_settings.use_m3_art,
        )

    async def draw_card(
        self, i: Interaction, card_settings: CardSettings, *, character: Character | None = None
    ) -> io.BytesIO:
        """Draw build card for a single character."""
        character_id = self.character_ids[0]
        character = character or self.characters[character_id]

        force_hb_temp = self.character_type is CharacterType.CACHE or isinstance(
            character, HoyolabGICharacter
        )
        if force_hb_temp and "hb" not in card_settings.template:
            card_settings.template = "hb1"
            await card_settings.save(update_fields=("template",))

        await self._fix_invalid_template(card_settings)

        template = card_settings.template
        draw_input = DrawInput(
            dark_mode=card_settings.dark_mode,
            locale=await self.get_character_locale(character),
            session=i.client.session,
            filename="card.png",
            executor=i.client.executor,
            loop=i.client.loop,
        )

        if self.game is Game.STARRAIL:
            if "hb" in template:
                return await self._draw_hb_hsr_character_card(character, card_settings, draw_input)
            return await self._draw_src_character_card(i.client.session, character, card_settings)
        if self.game is Game.GENSHIN:
            if "hb" in template:
                return await self._draw_hb_gi_character_card(character, card_settings, draw_input)
            return await self._draw_enka_card(i.client.session, character, card_settings)
        if self.game is Game.ZZZ:
            return await self._draw_hb_zzz_character_card(character, card_settings, draw_input)

        msg = f"draw_card not implemented for game {self.game} template {template}"
        raise ValueError(msg)

    async def get_character_locale(self, character: Character) -> Locale:
        if self._account is not None and self._account.platform is Platform.MIYOUSHE:
            return Locale.chinese

        key = str(character.id)
        if isinstance(character, HoyolabCharacter):
            key += "-hoyolab"

        cache_extras = await self.fetch_cache_extras()
        cache_extra = cache_extras.get(key)
        return self.locale if cache_extra is None else Locale(cache_extra["locale"])

    async def draw_team_card(self, i: Interaction) -> io.BytesIO:
        """Draw team card for multiple characters."""
        if self.game is not Game.GENSHIN:
            self._check_card_data()

        locale = (
            draw_locale(self.locale, self._account) if self._account is not None else self.locale
        )
        settings = await Settings.get(user_id=i.user.id)

        draw_input = DrawInput(
            dark_mode=settings.team_card_dark_mode,
            locale=locale,
            session=i.client.session,
            filename="card.png",
            executor=i.client.executor,
            loop=i.client.loop,
        )
        characters = [self.characters[char_id] for char_id in self.character_ids]

        if self.game is Game.ZZZ:
            assert self._account is not None
            client = self._account.client
            client.set_lang(self.locale)
            agents = [
                await client.get_zzz_agent_info(int(char_id)) for char_id in self.character_ids
            ]

            agent_card_settings = {
                int(char_id): await get_card_settings(i.user.id, char_id, game=self.game)
                for char_id in self.character_ids
            }
            agent_colors = {
                int(char_id): agent_card_settings[int(char_id)].custom_primary_color
                or self._card_data[char_id]["color"]
                for char_id in self.character_ids
            }
            show_substat_rolls = {
                int(char_id): agent_card_settings[int(char_id)].show_substat_rolls
                for char_id in self.character_ids
            }
            hl_special_stats = {
                int(char_id): agent_card_settings[int(char_id)].highlight_special_stats
                for char_id in self.character_ids
            }
            hl_substats = {
                int(char_id): agent_card_settings[int(char_id)].highlight_substats
                for char_id in self.character_ids
            }
            images = {
                str(char.id): await get_team_image(i.user.id, str(char.id), game=self.game)
                or get_default_art(
                    char, is_team=True, use_m3_art=agent_card_settings[int(char.id)].use_m3_art
                )
                for char in characters
            }

            return await draw_zzz_team_card(
                draw_input,
                agents,
                agent_colors,
                {int(k): v for k, v in images.items()},
                show_substat_rolls=show_substat_rolls,
                agent_special_stat_map=await JSONFile.read(ZZZ_AVATAR_BATTLE_TEMP_JSON),
                hl_special_stats=hl_special_stats,
                agent_hl_substat_map=hl_substats,
            )

        # GI and HSR
        images = {
            str(char.id): await get_team_image(i.user.id, str(char.id), game=self.game)
            or get_default_art(char, is_team=True)
            for char in characters
        }

        if self.game is Game.STARRAIL:
            character_colors = {
                char_id: (
                    await get_card_settings(i.user.id, char_id, game=self.game)
                ).custom_primary_color
                or self._card_data[char_id]["primary"]
                for char_id in self.character_ids
            }
            return await draw_hsr_team_card(
                draw_input,
                characters,  # pyright: ignore [reportArgumentType]
                images,
                character_colors,
            )
        if self.game is Game.GENSHIN:
            characters = [self.characters[char_id] for char_id in self.character_ids]
            return await draw_gi_team_card(
                draw_input,
                characters,  # pyright: ignore [reportArgumentType]
                images,
            )

        raise FeatureNotImplementedError(game=self.game)

    async def add_default_hl_substats(self, user_id: int) -> None:
        if self.zzz_data is None:
            return

        agent_special_stat_map: dict[str, list[int]] = await JSONFile.read(
            ZZZ_AVATAR_BATTLE_TEMP_JSON
        )
        character_ids = [agent.id for agent in self.zzz_data]

        for character_id in character_ids:
            card_settings = await get_card_settings(user_id, str(character_id), game=Game.ZZZ)
            if card_settings.highlight_substats:
                continue

            special_stat_ids = agent_special_stat_map.get(str(character_id), [])
            special_substat_ids = [
                ZZZ_AGENT_STAT_TO_DISC_SUBSTAT.get(stat_id) for stat_id in special_stat_ids
            ]

            hl_substats = [
                substat_id
                for _, substat_id, _ in ZZZ_DISC_SUBSTATS
                if substat_id in special_substat_ids
            ]
            card_settings.highlight_substats = hl_substats
            await card_settings.save(update_fields=("highlight_substats",))

    async def update(
        self,
        i: Interaction,
        item: Select[ProfileView] | Button[ProfileView] | None = None,
        *,
        unset_loading_state: bool = True,
        character: Character | None = None,
        content: str | None = None,
    ) -> None:
        card_settings = await get_card_settings(i.user.id, self.character_ids[0], game=self.game)
        is_team = len(self.character_ids) > 1

        try:
            bytes_obj = (
                await self.draw_team_card(i)
                if is_team
                else await self.draw_card(i, card_settings, character=character)
            )
            bytes_obj.seek(0)
        except Exception as e:
            if isinstance(e, DownloadImageFailedError):
                attr = "current_team_image" if is_team else "current_image"
                setattr(card_settings, attr, None)
                await card_settings.save(update_fields=(attr,))

            if isinstance(e, CardNotReadyError):
                logger.error(f"Card not ready for {e.character_name}")

            if "hb" not in card_settings.template:
                logger.warning("Failed to draw card")
                i.client.capture_exception(e)

                card_settings.template = "hb1"
                await card_settings.save(update_fields=("template",))
                raise ThirdPartyCardTempError from e
            raise

        attachments = [File(bytes_obj, filename="card.png")]

        if unset_loading_state and item is not None:
            await item.unset_loading_state(
                i, attachments=attachments, embed=self.card_embed, content=content
            )
        else:
            self.message = await i.edit_original_response(
                attachments=attachments, embed=self.card_embed, view=self, content=content
            )

    async def start(self, i: Interaction) -> None:
        self._set_characters()
        self._add_items()

        if self.game is Game.ZZZ:
            await self.add_default_hl_substats(i.user.id)

        dyk = await get_dyk(i)
        if self.character_ids:
            CharacterSelect.update_ui(
                self, character_id=self.character_ids[0], is_team=len(self.character_ids) > 1
            )
            return await self.update(i, unset_loading_state=False, content=dyk)

        await i.followup.send(embed=self.player_embed, view=self, content=dyk)
        self.message = await i.original_response()

        if self.game is Game.ZZZ:
            await show_dismissible(
                i,
                Dismissible(
                    id="m3_art",
                    description=LocaleStr(key="dismissible_m3_art_desc"),
                    image="https://img.seria.moe/kVbCOBrqEMHlQsVd.png",
                ),
            )

        if self.game is Game.STARRAIL:
            await show_dismissible(
                i,
                Dismissible(
                    id="hsr_temp2",
                    description=LocaleStr(key="dismissible_hsr_temp2_desc"),
                    image="https://img.seria.moe/HLHoTSwcXvAPHzJB.png",
                ),
            )
