from __future__ import annotations

import asyncio
import string
import uuid
from io import BytesIO
from itertools import starmap
from typing import TYPE_CHECKING, Any, Literal, cast

import aiohttp
import akasha
import attr
import enka
import hb_data
from discord import File
from genshin.models import ZZZPartialAgent
from loguru import logger

from hoyo_buddy import ui
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    HSR_SKIN_ART_URL,
    LOCALE_TO_ENKA_CARDS_LANG,
    LOCALE_TO_GI_CARD_API_LANG,
    LOCALE_TO_HSR_CARD_API_LANG,
    ZZZ_AVATAR_BATTLE_TEMP_JSON,
    locale_to_genshin_data_lang,
    locale_to_starrail_data_lang,
    locale_to_zenless_data_lang,
)
from hoyo_buddy.db import JSONFile, Settings, draw_locale, get_dyk
from hoyo_buddy.db.utils import (
    get_card_settings,
    get_default_color,
    is_supporter,
    set_highlight_substats,
)
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.draw.main_funcs import (
    draw_gi_build_card,
    draw_gi_team_card,
    draw_hsr_build_card,
    draw_hsr_team_card,
    draw_zzz_build_card,
    draw_zzz_team_card,
)
from hoyo_buddy.draw.static import ZZZ_V2_GAME_RECORD
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, Locale, Platform
from hoyo_buddy.exceptions import (
    DownloadImageFailedError,
    FeatureNotImplementedError,
    NoCardDataError,
    ThirdPartyCardTempError,
)
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.hoyo.clients.yatta import YattaAPIClient
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput, HoyolabGICharacter, HoyolabHSRCharacter, ZZZEnkaCharacter
from hoyo_buddy.types import Builds, HoyolabCharacter
from hoyo_buddy.ui import ToggleUIButton
from hoyo_buddy.ui.hoyo.profile.player_embed import PlayerEmbedMixin
from hoyo_buddy.ui.hoyo.profile.templates import TEMPLATES
from hoyo_buddy.utils import format_float, human_format_number
from hoyo_buddy.utils.misc import get_template_num

from .image_settings import get_default_art, get_default_collection, get_team_image
from .items.build_select import BuildSelect
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import MAX_VALUES, CharacterSelect
from .items.player_btn import PlayerInfoButton
from .items.redraw_card_btn import RedrawCardButton
from .items.skin_select import DEFAULT_SKIN_ID, SkinSelect

if TYPE_CHECKING:
    import io
    from collections.abc import Sequence

    import discord
    import yatta
    from discord import Member, User
    from genshin.models import PartialGenshinUserStats, RecordCard, StarRailUserStats, ZZZFullAgent

    from hoyo_buddy.db import CardSettings, HoyoAccount
    from hoyo_buddy.types import Character, Interaction
    from hoyo_buddy.ui import Button, Select

    from .items.skin_select import Skin


CARD_API_ENDPOINTS = {
    "encard": "http://localhost:7652/en-card",
    "enkacard": "http://localhost:7652/enka-card",
    "src": "http://localhost:7652/star-rail-card",
}

ENKA_CARDS_URL = "https://cards.enka.network"

TOP_PERCENT_RANK_DECIMALS = 4

_URL_EXISTS: dict[str, bool] = {}

SKIN_TEMPLATES: dict[Game, frozenset[str]] = {
    Game.GENSHIN: frozenset({"hb1", "hb2"}),
    Game.STARRAIL: frozenset({"hb1", "hb2"}),
    Game.ZZZ: frozenset({"hb1", "hb3", "hb4"}),
}
"""Templates that draw the character in its outfit."""


def _apply_zzz_skin[T: ZZZFullAgent | ZZZEnkaCharacter](agent: T, skin_id: int | None) -> T:
    """Return a copy of the agent wearing the given outfit, or the agent itself if not set.

    Falls back to the default outfit if the outfit has no card data.
    """
    if skin_id is None:
        skin_id = agent.outfit_id
    if skin_id not in {None, DEFAULT_SKIN_ID} and f"{agent.id}_{skin_id}" not in CARD_DATA.zzz:
        skin_id = DEFAULT_SKIN_ID
    if skin_id is None:
        return agent

    outfit_id = None if skin_id == DEFAULT_SKIN_ID else skin_id
    if isinstance(agent, ZZZEnkaCharacter):
        return attr.evolve(agent, outfit_id=outfit_id)

    suffix = "" if outfit_id is None else f"_{outfit_id}"
    banner_icon = (
        ZZZ_V2_GAME_RECORD / f"role_vertical_painting/role_vertical_painting_{agent.id}{suffix}.png"
    )
    return agent.model_copy(update={"banner_icon": str(banner_icon)})


async def _url_exists(session: aiohttp.ClientSession, url: str) -> bool:
    if url not in _URL_EXISTS:
        try:
            async with session.head(url) as resp:
                _URL_EXISTS[url] = resp.status == 200
        except aiohttp.ClientError:
            return False
    return _URL_EXISTS[url]


class ProfileView(ui.LayoutView, PlayerEmbedMixin):
    def __init__(
        self,
        uid: int,
        game: Game,
        *,
        # Hoyolab data
        hoyolab_hsr_characters: list[HoyolabHSRCharacter] | None = None,
        hoyolab_hsr_user: StarRailUserStats | None = None,
        hoyolab_gi_characters: list[HoyolabGICharacter] | None = None,
        hoyolab_gi_user: PartialGenshinUserStats | None = None,
        hoyolab_zzz_user: RecordCard | None = None,
        hoyolab_zzz_characters: Sequence[ZZZPartialAgent | ZZZEnkaCharacter] | None = None,
        # Enka data
        starrail_data: enka.hsr.ShowcaseResponse | None = None,
        genshin_data: enka.gi.ShowcaseResponse | None = None,
        zzz_data: enka.zzz.ShowcaseResponse | None = None,
        # Misc
        character_ids: list[str],
        account: HoyoAccount | None,
        builds: Builds | None = None,
        owner: enka.Owner | None = None,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        # Hoyolab data
        self.hoyolab_hsr_characters = hoyolab_hsr_characters or []
        self.hoyolab_hsr_user = hoyolab_hsr_user

        self.hoyolab_gi_characters = hoyolab_gi_characters or []
        self.hoyolab_gi_user = hoyolab_gi_user

        self.hoyolab_zzz_user = hoyolab_zzz_user
        self.hoyolab_zzz_characters = hoyolab_zzz_characters or []

        # Enka data
        self.starrail_data = starrail_data
        self.genshin_data = genshin_data
        self.zzz_data = zzz_data

        self.uid = uid
        self.game = game
        self.character_ids: list[str] = []
        self.characters: dict[str, Character] = {}
        self._param_character_ids = character_ids

        self._account = account
        self._builds = builds or {}

        self._owner_username: str | None = owner.username if owner is not None else None
        self._owner_hash: str | None = owner.hash if owner is not None else None
        self._build_id: int | Literal["current"] | None = None
        self._rows: list[list[Button | Select]] = []
        self.dyk = ""
        self._card_filename = "card.webp"

        self.current_character: Character | None = None
        self._skins: dict[str, list[Skin]] | None = None
        self._zzz_outfit_id: int | None = None
        """In-game outfit of the last drawn ZZZ agent."""

    async def _get_hsr_character_color(self, *, user_id: int, character_id: str) -> str:
        card_setting = await get_card_settings(user_id, character_id, game=self.game)

        if card_setting.custom_primary_color is not None:
            return card_setting.custom_primary_color

        color = card_setting.custom_primary_color or get_default_color(
            character_id,
            game=Game.STARRAIL,
            template=card_setting.template,
            dark_mode=card_setting.dark_mode,
            outfit_id=None,
        )
        if color is not None:
            return color

        raise NoCardDataError(character_id, character_id)

    async def _get_zzz_character_color(
        self, *, user_id: int, character: ZZZFullAgent | ZZZEnkaCharacter
    ) -> str:
        settings = await get_card_settings(user_id, str(character.id), game=self.game)

        color = settings.custom_primary_color or get_default_color(
            str(character.id),
            game=Game.ZZZ,
            template=settings.template,
            dark_mode=settings.dark_mode,
            outfit_id=character.outfit_id,
        )

        if color is not None:
            return color

        key = (
            str(character.id)
            if character.outfit_id is None
            else f"{character.id}_{character.outfit_id}"
        )
        raise NoCardDataError(character.name, key)

    async def _batch_fetch_lc_details(
        self, api: YattaAPIClient, lc_ids: list[int]
    ) -> dict[int, yatta.LightConeDetail]:
        return_dict: dict[int, yatta.LightConeDetail] = {}
        tasks = [asyncio.create_task(api.fetch_light_cone_detail(lc_id)) for lc_id in lc_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, BaseException):
                logger.error(f"Failed to fetch light cone detail: {result}")
                continue
            return_dict[result.id] = result

        return return_dict

    async def _request_draw_card_api(
        self, template: str, *, payload: dict[str, Any], session: aiohttp.ClientSession
    ) -> BytesIO:
        endpoint = CARD_API_ENDPOINTS.get(template.rstrip(string.digits))
        if endpoint is None:
            msg = f"Invalid template: {template}"
            raise ValueError(msg)

        async with session.post(endpoint, json=payload) as resp:
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _fix_invalid_template(self, card_settings: CardSettings) -> None:
        if self.game not in TEMPLATES or card_settings.template not in TEMPLATES[self.game]:
            card_settings.template = "hb1"
            await card_settings.save(update_fields=("template",))

    async def _get_character_rank(
        self, character: Character, *, with_detail: bool = False
    ) -> str | None:
        async with akasha.AkashaAPI(headers={"User-Agent": CONFIG.user_agent}) as api:
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
            key="top_percent",
            percent=format_float(character_calc.top_percent, decimals=TOP_PERCENT_RANK_DECIMALS),
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

    def _set_characters_with_enka(
        self, game: Literal[Game.STARRAIL, Game.GENSHIN, Game.ZZZ]
    ) -> None:
        if game is Game.STARRAIL:
            hoyolab_characters = self.hoyolab_hsr_characters
        elif game is Game.GENSHIN:
            hoyolab_characters = self.hoyolab_gi_characters
        else:  # Game.ZZZ
            hoyolab_characters = self.hoyolab_zzz_characters

        if game is Game.STARRAIL:
            data = self.starrail_data
        elif game is Game.GENSHIN:
            data = self.genshin_data
        else:  # Game.ZZZ
            data = self.zzz_data

        enka_char_ids: list[str] = []
        if data is not None:
            if isinstance(data, enka.zzz.ShowcaseResponse):
                characters = data.agents
            else:
                characters = data.characters

            for char in characters:
                enka_char_ids.append(str(char.id))
                character = (
                    GenshinClient.convert_zzz_character(char)
                    if isinstance(char, enka.zzz.Agent)
                    else char
                )
                self.characters[str(char.id)] = character

        for builds in self._builds.values():
            character = builds[0].character
            if str(character.id) not in enka_char_ids:
                if isinstance(character, enka.zzz.Agent):
                    character = GenshinClient.convert_zzz_character(character)
                self.characters[str(character.id)] = character

        for char in hoyolab_characters:
            if str(char.id) not in enka_char_ids:
                enka_char_ids.append(str(char.id))
                self.characters[str(char.id)] = char

    def _set_characters(self) -> None:
        if self.game is Game.STARRAIL:
            self._set_characters_with_enka(Game.STARRAIL)
        elif self.game is Game.GENSHIN:
            self._set_characters_with_enka(Game.GENSHIN)
        elif self.game is Game.ZZZ:
            self._set_characters_with_enka(Game.ZZZ)

        for character_id in self._param_character_ids:
            if (
                len(self.character_ids) >= MAX_VALUES[self.game]
                or character_id not in self.characters
            ):
                break
            self.character_ids.append(character_id)

    @property
    def card_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale)
        embed.set_image(url=f"attachment://{self._card_filename}")
        if self._account is not None:
            embed.add_acc_info(self._account)
        else:
            embed.set_author(name=f"UID: {self.uid}", icon_url=get_game_icon(self.game))
        return embed

    def _add_items(self) -> None:
        self._rows = [[PlayerInfoButton(row=0), CardSettingsButton(row=0), RedrawCardButton(row=0)]]

        if self.characters:
            characters = [
                i[1]
                for i in sorted(
                    self.characters.items(), key=lambda x: x[0] not in self.character_ids
                )
            ]
            self._rows.append(
                [
                    CharacterSelect(
                        self.game,
                        characters,
                        self.genshin_data,
                        self.starrail_data,
                        self.zzz_data,
                        self._account,
                        self.character_ids,
                        row=2,
                    )
                ]
            )

        self._rows.append([BuildSelect(row=3)])
        if self.game in SKIN_TEMPLATES:
            self._rows.append([SkinSelect(row=4)])
        self._rows.append([CardInfoButton(row=4), ToggleUIButton()])

    def render(self, embed: discord.Embed) -> None:
        self.clear_items()
        self.add_item(ui.EmbedContainer(embed, *starmap(ui.ActionRow, self._rows)))
        if self.dyk:
            self.add_item(ui.TextDisplay(self.dyk))

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
        if (
            all((self._owner_hash, self._owner_username, self._build_id))
            and self._build_id != "current"
        ):
            payload["owner"] = {
                "username": self._owner_username,
                "hash": self._owner_hash,
                "build_id": self._build_id,
            }

        if isinstance(character, HoyolabHSRCharacter):
            assert self._account is not None
            payload["cookies"] = self._account.cookies

        return await self._request_draw_card_api(template, payload=payload, session=session)

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
        if (
            all((self._owner_hash, self._owner_username, self._build_id))
            and self._build_id != "current"
        ):
            payload["owner"] = {
                "username": self._owner_username,
                "hash": self._owner_hash,
                "build_id": self._build_id,
            }

        return await self._request_draw_card_api(template, payload=payload, session=session)

    async def _draw_enka_cards_card(
        self, session: aiohttp.ClientSession, character: Character, card_settings: CardSettings
    ) -> BytesIO:
        """Draw GI/HSR/ZZZ character card using the enka.cards service (enka.network style)."""
        params = {
            "lang": LOCALE_TO_ENKA_CARDS_LANG.get(await self.get_character_locale(character), "en"),
            "substats": str(card_settings.show_substat_rolls).lower(),
        }
        # enka.network URLs use the plain avatar ID, without the traveler depot suffix
        character_id = str(character.id).split("-")[0]

        if (
            all((self._owner_username, self._owner_hash, self._build_id))
            and self._build_id != "current"
        ):
            # Saved build on enka.network (game-agnostic /u/ route)
            url = (
                f"{ENKA_CARDS_URL}/u/{self._owner_username}/{self._owner_hash}"
                f"/{character_id}/{self._build_id}/image"
            )
        else:
            game_paths = {Game.GENSHIN: "u", Game.STARRAIL: "hsr", Game.ZZZ: "zzz"}
            url = f"{ENKA_CARDS_URL}/{game_paths[self.game]}/{self.uid}/{character_id}/image"

        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_hb_hsr_character_card(
        self,
        character: Character,
        card_settings: CardSettings,
        draw_input: DrawInput,
        *,
        user_id: int,
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert isinstance(character, enka.hsr.Character | HoyolabHSRCharacter)

        if character.light_cone is not None and isinstance(character, HoyolabHSRCharacter):
            async with YattaAPIClient() as api:
                manual_avatar = await api.fetch_manual_avatar()
                lc_detail = await api.fetch_light_cone_detail(character.light_cone.id)

            character.light_cone.stats = GenshinClient.get_lc_stats(
                character.light_cone, lc_detail, manual_avatar
            )

        character_id = str(character.id)
        character_data = CARD_DATA.hsr.get(character_id)
        if character_data is None:
            raise NoCardDataError(character.name, character_id)

        skin_art = await self._get_skin_art(character, card_settings)
        image_url = (
            card_settings.current_image
            or skin_art
            or get_default_art(character, is_team=False, use_m3_art=card_settings.use_m3_art)
        )

        if card_settings.custom_primary_color is None:
            primary = character_data.primary
            if card_settings.dark_mode:
                primary = character_data.primary_dark or primary
        else:
            primary = card_settings.custom_primary_color

        template_num = get_template_num(card_settings.template)
        template_num = cast("Literal[1, 2]", template_num)

        # Animations are rendered from the character's default outfit
        animation = None
        if skin_art is None and card_settings.animated_image and await is_supporter(user_id):
            animation = CARD_DATA.hsr_spine(template_num).get(character_id)

        return await draw_hsr_build_card(
            draw_input, character, image_url, primary, template=template_num, animation=animation
        )

    async def _draw_hb_gi_character_card(
        self,
        character: Character,
        card_settings: CardSettings,
        draw_input: DrawInput,
        *,
        user_id: int,
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert isinstance(character, enka.gi.Character | HoyolabGICharacter)

        skin_art = await self._get_skin_art(character, card_settings)
        image_url = (
            card_settings.current_image
            or skin_art
            or get_default_art(character, is_team=False, use_m3_art=card_settings.use_m3_art)
        )

        template_num = get_template_num(card_settings.template)
        template_num = cast("Literal[1, 2]", template_num)

        if template_num == 2:
            zoom = 0.7 if card_settings.current_image is None else 1.0
        else:
            zoom = 0.8 if card_settings.current_image is None else 1.0

        rank = None
        if card_settings.show_rank:
            try:
                rank = await self._get_character_rank(character, with_detail=template_num == 1)
            except (akasha.AkashaAPIError, TimeoutError, aiohttp.ClientError):
                rank = None
            except Exception:
                logger.exception("Failed to fetch character rank from Akasha API")

        # Animations are rendered from the character's TCG card face, in the default outfit
        default_art = get_default_art(character.model_copy(update={"costume": None}), is_team=False)
        animation = None
        if (
            template_num == 1
            and skin_art in {None, default_art}
            and card_settings.animated_image
            and await is_supporter(user_id)
        ):
            animation = CARD_DATA.gi_spine.get(str(character.id))

        return await draw_gi_build_card(
            draw_input,
            character,
            image_url=image_url,
            zoom=zoom,
            template=template_num,
            top_crop=template_num == 2
            and card_settings.current_image
            in get_default_collection(str(character.id), game=self.game),
            rank=rank,
            animation=animation,
        )

    async def _draw_hb_zzz_character_card(
        self,
        character: Character,
        card_settings: CardSettings,
        draw_input: DrawInput,
        *,
        user_id: int,
    ) -> BytesIO:
        """Draw ZZZ build card in Hoyo Buddy template."""
        assert isinstance(character, ZZZPartialAgent | ZZZEnkaCharacter)

        agent: ZZZFullAgent | ZZZEnkaCharacter | None = None

        if isinstance(character, ZZZEnkaCharacter):
            agent = character
        else:
            if self._account is None:
                msg = "Cannot fetch full agent details without a logged-in account."
                raise ValueError(msg)

            client = self._account.client
            client.set_lang(self.locale)
            agent = await client.get_zzz_agent_info(character.id)

        self._zzz_outfit_id = agent.outfit_id
        agent = _apply_zzz_skin(agent, card_settings.skin_id)

        key = str(agent.id)
        template_num = get_template_num(card_settings.template)
        template_num = cast("Literal[1, 2, 3, 4]", template_num)

        if template_num == 2:
            agent_temp_data = CARD_DATA.zzz2.get(key)
            if agent_temp_data is None:
                raise NoCardDataError(agent.name, key)

            if not agent_temp_data.color:
                agent_temp1_data = CARD_DATA.zzz.get(key)
                if agent_temp1_data is None:
                    raise NoCardDataError(agent.name, key)

                agent_temp_data = agent_temp_data.model_copy(
                    update={"color": agent_temp1_data.color}
                )
        else:
            # 1, 3, 4
            if agent.outfit_id is not None:
                key = f"{agent.id}_{agent.outfit_id}"
            agent_temp_data = CARD_DATA.zzz.get(key)

        if agent_temp_data is None:
            raise NoCardDataError(agent.name, key)

        agent_special_stat_map: dict[str, list[int]] = await JSONFile.read(
            ZZZ_AVATAR_BATTLE_TEMP_JSON
        )

        # Animations are rendered from the agent's default outfit
        animation = None
        if (
            template_num == 1
            and agent.outfit_id is None
            and card_settings.animated_image
            and await is_supporter(user_id)
        ):
            animation = CARD_DATA.zzz_spine.get(str(agent.id))

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
            animation=animation,
        )

    async def draw_card(
        self, i: Interaction, card_settings: CardSettings, *, character: Character | None = None
    ) -> io.BytesIO:
        """Draw build card for a single character."""
        character_id = self.character_ids[0]
        character = character or self.characters[character_id]
        self.current_character = character

        # enka.cards renders only from enka.network showcase data, so HoYoLAB-sourced
        # characters can't use it; fall back to the Hoyo Buddy template.
        force_hb_temp = isinstance(character, HoyolabGICharacter) or (
            card_settings.template == "enka1" and isinstance(character, HoyolabCharacter)
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
            filename="card.webp",
            executor=i.client.executor,
            loop=i.client.loop,
        )

        if self.game is Game.STARRAIL:
            if template == "enka1":
                return await self._draw_enka_cards_card(i.client.session, character, card_settings)
            if "hb" in template:
                return await self._draw_hb_hsr_character_card(
                    character, card_settings, draw_input, user_id=i.user.id
                )
            return await self._draw_src_character_card(i.client.session, character, card_settings)

        if self.game is Game.GENSHIN:
            if template == "enka1":
                return await self._draw_enka_cards_card(i.client.session, character, card_settings)
            if "hb" in template:
                return await self._draw_hb_gi_character_card(
                    character, card_settings, draw_input, user_id=i.user.id
                )
            return await self._draw_enka_card(i.client.session, character, card_settings)

        if self.game is Game.ZZZ:
            if template == "enka1":
                return await self._draw_enka_cards_card(i.client.session, character, card_settings)
            return await self._draw_hb_zzz_character_card(
                character, card_settings, draw_input, user_id=i.user.id
            )

        msg = f"draw_card not implemented for game {self.game} template {template}"
        raise ValueError(msg)

    async def get_character_locale(self, character: Character) -> Locale:
        if self._account is not None and self._account.platform is Platform.MIYOUSHE:
            return Locale.chinese

        key = str(character.id)
        if isinstance(character, HoyolabCharacter):
            key += "-hoyolab"

        return self.locale

    async def draw_team_card(self, i: Interaction) -> io.BytesIO:
        """Draw team card for multiple characters."""
        locale = (
            draw_locale(self.locale, self._account) if self._account is not None else self.locale
        )
        settings = await Settings.get(user_id=i.user.id)

        draw_input = DrawInput(
            dark_mode=settings.team_card_dark_mode,
            locale=locale,
            session=i.client.session,
            filename="card.webp",
            executor=i.client.executor,
            loop=i.client.loop,
        )
        characters = [self.characters[char_id] for char_id in self.character_ids]

        if self.game is Game.ZZZ:
            agents: list[ZZZFullAgent | ZZZEnkaCharacter] = []

            for char_id in self.character_ids:
                character = self.characters[char_id]
                if isinstance(character, ZZZPartialAgent):
                    assert self._account is not None
                    client = self._account.client
                    client.set_lang(self.locale)
                    agents.append(await client.get_zzz_agent_info(int(char_id)))
                elif isinstance(character, ZZZEnkaCharacter):
                    agents.append(character)

            agent_card_settings = {
                int(char_id): await get_card_settings(i.user.id, char_id, game=self.game)
                for char_id in self.character_ids
            }
            agents = [_apply_zzz_skin(a, agent_card_settings[a.id].skin_id) for a in agents]
            agent_colors: dict[int, str] = {
                a.id: await self._get_zzz_character_color(user_id=i.user.id, character=a)
                for a in agents
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
                str(a.id): await get_team_image(i.user.id, str(a.id), game=self.game)
                or get_default_art(
                    a, is_team=True, use_m3_art=agent_card_settings[int(a.id)].use_m3_art
                )
                for a in agents
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
        images: dict[str, str] = {}
        for char in characters:
            char_settings = await get_card_settings(i.user.id, str(char.id), game=self.game)
            images[str(char.id)] = (
                char_settings.current_team_image
                or await self._get_skin_art(char, char_settings)
                or get_default_art(char, is_team=True)
            )

        if self.game is Game.STARRAIL:
            character_colors: dict[str, str] = {}

            for char_id in self.character_ids:
                character_colors[char_id] = await self._get_hsr_character_color(
                    user_id=i.user.id, character_id=char_id
                )

            # Batch fetch
            fetch_ids = [
                int(char.light_cone.id)
                for char in characters
                if isinstance(char, HoyolabHSRCharacter) and char.light_cone is not None
            ]
            if fetch_ids:
                async with YattaAPIClient() as api:
                    manual_avatars = await api.fetch_manual_avatar()
                    lc_details = await self._batch_fetch_lc_details(api, fetch_ids)

                for char in characters:
                    if (
                        isinstance(char, HoyolabHSRCharacter)
                        and char.light_cone is not None
                        and char.light_cone.id in lc_details
                    ):
                        lc_detail = lc_details[char.light_cone.id]
                        char.light_cone.stats = GenshinClient.get_lc_stats(
                            char.light_cone, lc_detail, manual_avatars
                        )

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
        character_ids: list[int] = []

        agent_special_stat_map: dict[str, list[int]] = await JSONFile.read(
            ZZZ_AVATAR_BATTLE_TEMP_JSON
        )
        character_ids = [agent.id for agent in self.hoyolab_zzz_characters]

        if self.zzz_data is not None:
            character_ids.extend([agent.id for agent in self.zzz_data.agents])

        for character_id in character_ids:
            card_settings = await get_card_settings(user_id, str(character_id), game=Game.ZZZ)
            if card_settings.highlight_substats:
                continue

            await set_highlight_substats(
                agent_special_stat_map=agent_special_stat_map,
                card_settings=card_settings,
                character_id=character_id,
            )

    async def _fetch_skins(self) -> dict[str, list[Skin]]:
        if self.game is Game.GENSHIN:
            async with hb_data.GIClient() as client:
                gi_characters = client.get_characters(
                    lang=hb_data.gi.Language(locale_to_genshin_data_lang(self.locale))
                )
            return {str(char.id): list(char.costumes) for char in gi_characters}

        if self.game is Game.STARRAIL:
            async with hb_data.HSRClient() as client:
                hsr_characters = client.get_characters(
                    lang=hb_data.hsr.Language(locale_to_starrail_data_lang(self.locale))
                )
            # The build card is laid out for the zoomed gacha art, which not every skin has yet
            skins = [
                skin.model_copy(update={"image": HSR_SKIN_ART_URL.format(skin_id=skin.id)})
                for char in hsr_characters
                for skin in char.skins
            ]
            async with aiohttp.ClientSession() as session:
                exists = await asyncio.gather(*(_url_exists(session, s.image) for s in skins))
            return {
                str(char.id): [
                    s
                    for s, ok in zip(skins, exists, strict=True)
                    if ok and s.character_id == char.id
                ]
                for char in hsr_characters
            }

        if self.game is Game.ZZZ:
            async with hb_data.ZZZClient() as client:
                zzz_characters = client.get_characters(
                    lang=hb_data.zzz.Language(locale_to_zenless_data_lang(self.locale))
                )
            # Only agents with card data for the outfit can be drawn in it
            card_data = CARD_DATA.zzz
            return {
                str(char.id): [skin for skin in char.skins if f"{char.id}_{skin.id}" in card_data]
                for char in zzz_characters
            }

        return {}

    async def _get_skins(self, character_id: str) -> list[Skin]:
        if self._skins is None:
            self._skins = await self._fetch_skins()
        # Strip the traveler depot suffix
        return self._skins.get(character_id.split("-", maxsplit=1)[0], [])

    async def _get_in_game_skin_id(self, character: Character | None) -> int | None:
        if self.game is Game.ZZZ:
            return self._zzz_outfit_id
        if isinstance(character, enka.gi.Character):
            return character.costume_id
        if isinstance(character, HoyolabGICharacter):
            return character.costume.id if character.costume is not None else None
        if isinstance(character, HoyolabHSRCharacter) and character.is_wearing_outfit:
            # HoYoLAB only tells whether an outfit is worn, not which one
            skins = await self._get_skins(character.id)
            return skins[0].id if len(skins) == 1 else None
        return None

    async def _get_skin_art(self, character: Character, card_settings: CardSettings) -> str | None:
        """Get the GI/HSR character's art for its outfit, None for the default art."""
        skin_id = card_settings.skin_id
        if skin_id is None:
            skin_id = await self._get_in_game_skin_id(character)

        if skin_id is None:
            return None
        if skin_id == DEFAULT_SKIN_ID:
            if isinstance(character, enka.gi.Character | HoyolabGICharacter):
                return get_default_art(
                    character.model_copy(update={"costume": None}), is_team=False
                )
            return None

        skins = await self._get_skins(str(character.id))
        return next((skin.image for skin in skins if skin.id == skin_id), None)

    async def _update_skin_select(self, card_settings: CardSettings, *, is_team: bool) -> None:
        skin_select: SkinSelect = self.get_item("profile_skin_select")

        skins: list[Skin] = []
        if not is_team and card_settings.template in SKIN_TEMPLATES[self.game]:
            skins = await self._get_skins(self.character_ids[0])

        if skins:
            if card_settings.skin_id is not None:
                current = card_settings.skin_id
            else:
                current = await self._get_in_game_skin_id(self.current_character) or DEFAULT_SKIN_ID
            skin_select.set_options(skins, current=current)
            skin_select.translate(self.locale)

        # Also update the saved state, enable_items() restores it after the loading state
        self.item_states[skin_select.custom_id] = skin_select.disabled = not skins

    async def update(
        self,
        i: Interaction,
        item: Select[ProfileView] | Button[ProfileView] | None = None,
        *,
        unset_loading_state: bool = True,
        character: Character | None = None,
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

            if isinstance(e, NoCardDataError):
                logger.error(
                    f"Card not ready for {e.character_id}",
                    user_id=i.user.id,
                    uid=self.uid,
                    is_cookies=bool(self._account),
                    game=self.game.value,
                )

            if "hb" not in card_settings.template:
                logger.warning("Failed to draw card")
                i.client.capture_exception(e)

                card_settings.template = "hb1"
                await card_settings.save(update_fields=("template",))
                raise ThirdPartyCardTempError from e
            raise

        # Discord caches attachments by filename, so reusing one can show the previous card
        self._card_filename = f"card_{uuid.uuid4().hex[:8]}.webp"
        attachments = [File(bytes_obj, filename=self._card_filename)]
        if self.game in SKIN_TEMPLATES:
            await self._update_skin_select(card_settings, is_team=is_team)
        self.render(self.card_embed)

        if unset_loading_state and item is not None:
            await item.unset_loading_state(i, attachments=attachments)
        else:
            self.message = await i.edit_original_response(attachments=attachments, view=self)

    async def start(self, i: Interaction) -> None:
        self._set_characters()
        self._add_items()

        if self.game is Game.ZZZ:
            await self.add_default_hl_substats(i.user.id)

        self.dyk = await get_dyk(i)
        self.render(self.player_embed)

        if self.character_ids:
            CharacterSelect.update_ui(
                self, character_id=self.character_ids[0], is_team=len(self.character_ids) > 1
            )
            return await self.update(i, unset_loading_state=False)

        await i.followup.send(view=self)
        self.message = await i.original_response()
