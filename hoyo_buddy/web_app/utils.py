from __future__ import annotations

from typing import TYPE_CHECKING, Any

import ambr
import hb_data
from cryptography.fernet import Fernet

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import locale_to_starrail_data_lang, locale_to_zenless_data_lang
from hoyo_buddy.db.models import JSONFile
from hoyo_buddy.enums import Game
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db.models import GachaHistory
    from hoyo_buddy.enums import Locale


def decrypt_string(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted string using the configured key."""
    key = Fernet(CONFIG.fernet_key)
    return key.decrypt(encrypted.encode()).decode()


def encrypt_string(string: str) -> str:
    """Encrypt a string using the configured Fernet key."""
    key = Fernet(CONFIG.fernet_key)
    return key.encrypt(string.encode()).decode()


async def fetch_json_file(filename: str) -> Any:
    """Fetch a JSON file stored in the database jsonfile table."""
    return await JSONFile.read(filename)


async def fetch_gacha_names(
    *, gachas: Sequence[GachaHistory], locale: Locale, game: Game
) -> dict[int, str]:
    """Fetch item names for the given gacha history entries."""
    result: dict[int, str] = {}
    item_ids = list({g.item_id for g in gachas})

    if not item_ids:
        return result

    if game is Game.ZZZ:
        zzz_map: dict[str, str] = await fetch_json_file(
            f"zzz_item_names_{locale_to_zenless_data_lang(locale)}.json"
        )
        item_names = {int(k): v for k, v in zzz_map.items()}
    elif game is Game.STARRAIL:
        hsr_map: dict[str, str] = await fetch_json_file(
            f"hsr_item_names_{locale_to_starrail_data_lang(locale)}.json"
        )
        item_names = {int(k): v for k, v in hsr_map.items()}
    elif game is Game.GENSHIN:
        async with AmbrAPIClient(locale) as client:
            item_names = await client.fetch_item_id_to_name_map()
        async with hb_data.GIClient() as client:
            mw_costumes = client.get_mw_costumes()
            mw_items = client.get_mw_items()
            item_names.update({costume.id: costume.name for costume in mw_costumes})
            item_names.update({item.id: item.name for item in mw_items})
    else:
        msg = f"Unsupported game: {game} for fetching gacha names"
        raise ValueError(msg)

    for item_id in item_ids:
        result[item_id] = item_names.get(item_id, "???")

    return result


async def fetch_gacha_icons() -> dict[str, str]:
    """Fetch Genshin character/weapon icons from the ambr API."""
    gacha_icons: dict[str, str] = {}

    async with ambr.AmbrAPI() as api:
        weapons = await api.fetch_weapons()
        characters = await api.fetch_characters()

        gacha_icons.update({character.id: character.icon for character in characters})
        gacha_icons.update({str(weapon.id): weapon.icon for weapon in weapons})

    async with hb_data.GIClient() as client:
        mw_items = client.get_mw_items()
        gacha_icons.update({str(item.id): item.icon for item in mw_items})

        for item in mw_items:
            if "Component Catalog" in item.name:
                costume_id = item.id - 10000
                gacha_icons[str(item.id)] = gacha_icons.get(str(costume_id), "")

    return gacha_icons


def get_gacha_icon(*, game: Game, item_id: int) -> str:
    """Get the icon URL for a gacha item."""
    if game is Game.ZZZ:
        return f"https://stardb.gg/api/static/zzz/{item_id}.png"

    if game is Game.GENSHIN:
        return f"https://stardb.gg/api/static/genshin/{item_id}.png"

    if game is Game.STARRAIL:
        if len(str(item_id)) == 5:  # light cone
            return f"https://stardb.gg/api/static/StarRailResWebp/icon/light_cone/{item_id}.webp"

        # character
        return f"https://stardb.gg/api/static/StarRailResWebp/icon/character/{item_id}.webp"

    msg = f"Unsupported game: {game}"
    raise ValueError(msg)
