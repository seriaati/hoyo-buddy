from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from genshin.models import ZZZFullAgent, ZZZPartialAgent

from hoyo_buddy.constants import (
    HSR_DEFAULT_ART_URL,
    MANIKEN_BOY_GACHA_ART,
    MANIKEN_GIRL_GACHA_ART,
    PLAYER_BOY_GACHA_ART,
    PLAYER_GIRL_GACHA_ART,
    ZZZ_M3_ART_URL,
    ZZZ_M6_ART_URL,
    ZZZ_TEAM_IMAGE_OVERRIDES,
)
from hoyo_buddy.db.models import JSONFile
from hoyo_buddy.db.utils import get_card_settings
from hoyo_buddy.draw.card_data import CARD_DATA
from hoyo_buddy.draw.static import ZZZ_V2_GAME_RECORD
from hoyo_buddy.enums import Game
from hoyo_buddy.models import HoyolabGICharacter, HoyolabHSRCharacter, ZZZEnkaCharacter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.types import Character


GI_CHARACTER_ART_OVERRIDES: dict[str, str] = {
    "10000005": PLAYER_BOY_GACHA_ART,  # PlayerBoy
    "10000007": PLAYER_GIRL_GACHA_ART,  # PlayerGirl
    "10000117": MANIKEN_BOY_GACHA_ART,  # Maniken Boy
    "10000118": MANIKEN_GIRL_GACHA_ART,  # Maniken Girl
}


GI_DEFAULT_ARTS_FILE = "gi_default_arts.json"


async def get_team_image(user_id: int, character_id: str, *, game: Game) -> str | None:
    card_settings = await get_card_settings(user_id, character_id, game=game)
    return card_settings.current_team_image


async def save_gi_default_arts(
    characters: Sequence[enka.gi.Character | HoyolabGICharacter],
) -> None:
    """Cache GI gacha art so image settings can show it without a live character."""
    arts: dict[str, str] = await JSONFile.read(GI_DEFAULT_ARTS_FILE)
    new_arts = {str(character.id): character.icon.gacha for character in characters}
    if any(arts.get(char_id) != art for char_id, art in new_arts.items()):
        arts.update(new_arts)
        await JSONFile.write(GI_DEFAULT_ARTS_FILE, arts)


async def get_zzz_default_art(
    character_id: str, *, template: str, use_m3_art: bool, character: Character | None = None
) -> str | None:
    """Mirror the official art `fetch_zzz_draw_data` uses for each ZZZ template."""
    # Local import to avoid circular import through hoyo_buddy.draw.funcs
    # ruff:ignore[import-outside-top-level]
    from hoyo_buddy.draw.main_funcs import fetch_zzz_agent_images

    if template in {"hb1", "enka1"}:
        outfit_id = getattr(character, "outfit_id", None)
        key = str(outfit_id) if outfit_id is not None else character_id
        images: dict[str, str] = await JSONFile.read("zzz_images.json")
        if key not in images:
            return (await fetch_zzz_agent_images(1)).get(int(key))
        return images[key]

    if template == "hb2":
        filename = "zzz_m3_cinema_art.json" if use_m3_art else "zzz_m6_cinema_art.json"
        images = await JSONFile.read(filename)
        url = images.get(character_id) or (
            await fetch_zzz_agent_images(2, use_m3_art=use_m3_art)
        ).get(int(character_id))
        return url or (ZZZ_M3_ART_URL if use_m3_art else ZZZ_M6_ART_URL).format(
            char_id=character_id
        )

    # hb3 and hb4 use the vertical banner art, same as team cards
    if isinstance(character, ZZZPartialAgent | ZZZFullAgent | ZZZEnkaCharacter):
        return get_default_art(character, is_team=True)
    return await get_default_art_fallback(character_id, game=Game.ZZZ, is_team=True)


def get_default_art(
    character: Character | ZZZFullAgent, *, is_team: bool, use_m3_art: bool = False
) -> str:
    if isinstance(character, ZZZPartialAgent | ZZZFullAgent | ZZZEnkaCharacter):
        if is_team:
            outfit_id = getattr(character, "outfit_id", None)
            key = f"{character.id}_{outfit_id}" if outfit_id is not None else str(character.id)
            return ZZZ_TEAM_IMAGE_OVERRIDES.get(
                key, ZZZ_TEAM_IMAGE_OVERRIDES.get(str(character.id), character.banner_icon)
            )
        if use_m3_art:
            return ZZZ_M3_ART_URL.format(char_id=character.id)
        return ZZZ_M6_ART_URL.format(char_id=character.id)

    if isinstance(character, enka.gi.Character | HoyolabGICharacter):
        if character.costume is not None:
            return character.costume.icon.gacha
        char_id_str = str(character.id)
        for key, art in GI_CHARACTER_ART_OVERRIDES.items():
            if key in char_id_str:
                return art
        return character.icon.gacha

    if isinstance(character, enka.hsr.Character | HoyolabHSRCharacter):  # pyright: ignore[reportUnnecessaryIsInstance]
        return HSR_DEFAULT_ART_URL.format(char_id=character.id)

    msg = f"Unsupported character type: {type(character)}"
    raise TypeError(msg)


async def get_default_art_fallback(
    character_id: str, *, game: Game, is_team: bool, use_m3_art: bool = False
) -> str | None:
    """Best-effort default art when the live character object is unavailable."""
    if game is Game.ZZZ:
        if is_team:
            return ZZZ_TEAM_IMAGE_OVERRIDES.get(
                character_id,
                str(
                    ZZZ_V2_GAME_RECORD
                    / f"role_vertical_painting/role_vertical_painting_{character_id}.png"
                ),
            )
        if use_m3_art:
            return ZZZ_M3_ART_URL.format(char_id=character_id)
        return ZZZ_M6_ART_URL.format(char_id=character_id)

    if game is Game.STARRAIL:
        return HSR_DEFAULT_ART_URL.format(char_id=character_id)

    if game is Game.GENSHIN:
        for key, art in GI_CHARACTER_ART_OVERRIDES.items():
            if key in character_id:
                return art

        arts: dict[str, str] = await JSONFile.read(GI_DEFAULT_ARTS_FILE)
        return arts.get(character_id)

    return None


def get_default_collection(character_id: str, *, game: Game) -> list[str]:
    if game is Game.GENSHIN:
        card_data = CARD_DATA.gi
    elif game is Game.STARRAIL:
        card_data = CARD_DATA.hsr
    else:
        return []

    char_data = card_data.get(character_id)
    if char_data is None:
        return []

    return char_data.arts
