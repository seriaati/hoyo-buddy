from __future__ import annotations

import string
from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
import akasha
import enka
from discord import File
from genshin.models import ZZZFullAgent, ZZZPartialAgent
from loguru import logger

from hoyo_buddy.constants import (
    LOCALE_TO_GI_CARD_API_LANG,
    LOCALE_TO_HSR_CARD_API_LANG,
    ZZZ_AGENT_STAT_TO_DISC_SUBSTAT,
    ZZZ_AVATAR_BATTLE_TEMP_JSON,
    ZZZ_DISC_SUBSTATS,
)
from hoyo_buddy.db import JSONFile, Settings, draw_locale, get_dyk
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.draw.main_funcs import (
    draw_gi_build_card,
    draw_gi_team_card,
    draw_hsr_build_card,
    draw_hsr_team_card,
    draw_zzz_build_card,
    draw_zzz_team_card,
)
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game, Locale, Platform
from hoyo_buddy.exceptions import (
    CardNotReadyError,
    DownloadImageFailedError,
    FeatureNotImplementedError,
    ThirdPartyCardTempError,
)
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.icons import get_game_icon
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput, HoyolabGICharacter, HoyolabHSRCharacter, ZZZEnkaCharacter
from hoyo_buddy.types import Builds, Character, HoyolabCharacter
from hoyo_buddy.ui import Button, Select, ToggleUIButton, View
from hoyo_buddy.ui.hoyo.profile.items.image_settings_btn import ImageSettingsButton
from hoyo_buddy.ui.hoyo.profile.items.team_card_settings_btn import TeamCardSettingsButton
from hoyo_buddy.ui.hoyo.profile.player_embed import PlayerEmbedMixin
from hoyo_buddy.ui.hoyo.profile.templates import TEMPLATES
from hoyo_buddy.utils import format_float, human_format_number

from .card_settings import get_card_settings
from .image_settings import get_default_art, get_default_collection, get_team_image
from .items.build_select import BuildSelect
from .items.card_info_btn import CardInfoButton
from .items.card_settings_btn import CardSettingsButton
from .items.chara_select import MAX_VALUES, CharacterSelect
from .items.player_btn import PlayerInfoButton
from .items.redraw_card_btn import RedrawCardButton

if TYPE_CHECKING:
    import io
    from collections.abc import Sequence

    from discord import Member, User
    from genshin.models import PartialGenshinUserStats, RecordCard, StarRailUserStats

    from hoyo_buddy.db import CardSettings, HoyoAccount
    from hoyo_buddy.types import Builds, Interaction


CARD_API_ENDPOINTS = {
    "hattvr": "http://localhost:7652/hattvr-enka-card",
    "encard": "http://localhost:7652/en-card",
    "enkacard": "http://localhost:7652/enka-card",
    "src": "http://localhost:7652/star-rail-card",
}


class ProfileView(View, PlayerEmbedMixin):
    def __init__(
        self,
        uid: int,
        game: Game,
        card_data: dict[str, Any],
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

        self._card_data = card_data
        self._account = account
        self._builds = builds or {}

        self._owner_username: str | None = owner.username if owner is not None else None
        self._owner_hash: str | None = owner.hash if owner is not None else None
        self._build_id: int | Literal["current"] | None = None

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
        embed.set_image(url="attachment://card.webp")
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
                    self.genshin_data,
                    self.starrail_data,
                    self.zzz_data,
                    self._account,
                    self.character_ids,
                    row=2,
                )
            )

        self.add_item(BuildSelect(row=3))
        self.add_item(CardInfoButton(row=4))
        self.add_item(ToggleUIButton())

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
            except (akasha.AkashaAPIError, TimeoutError, aiohttp.ClientError):
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

        template_num: Literal[1, 2, 3, 4] = int(card_settings.template[-1])  # pyright: ignore[reportAssignmentType]
        exc = CardNotReadyError(agent.name)

        if template_num == 2:
            agent_temp2_data = CARD_DATA.zzz2.get(str(agent.id))
            if agent_temp2_data is None:
                raise exc

            if not agent_temp2_data.get("color"):
                agent_temp1_data = self._card_data.get(str(agent.id))
                if agent_temp1_data is None:
                    raise exc
                agent_temp2_data["color"] = agent_temp1_data["color"]
            agent_temp_data = agent_temp2_data
        else:
            # 1, 3, 4
            agent_temp_data: dict[str, Any] | None = self._card_data.get(str(agent.id))

            if agent_temp_data is not None and agent.outfit_id is not None:
                agent_outfit_data = self._card_data.get(f"{agent.id}_{agent.outfit_id}")
                if agent_outfit_data is None:
                    raise exc
                agent_temp_data.update(agent_outfit_data)

        if agent_temp_data is None:
            raise exc

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

        force_hb_temp = isinstance(character, HoyolabGICharacter)
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

        return self.locale

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
            # Only one card setting is stored per character, no matter the outfit.
            # However, since different outfits have different default colors,
            # we need to use the outfit_id to get the correct color.
            # Outfit data doesn't always have 'color' field, so we default to the main character color.
            agent_colors = {
                a.id: agent_card_settings[a.id].custom_primary_color
                or self._card_data[
                    f"{a.id}_{a.outfit_id}" if a.outfit_id is not None else str(a.id)
                ].get("color", self._card_data[str(a.id)]["color"])
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

        attachments = [File(bytes_obj, filename="card.webp")]

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
