from __future__ import annotations

from typing import Any

import ambr
import hb_data
from cryptography.fernet import Fernet

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.models import JSONFile


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
