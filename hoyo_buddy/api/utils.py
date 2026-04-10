from __future__ import annotations

from typing import Any

from cryptography.fernet import Fernet

from hoyo_buddy.config import CONFIG
from hoyo_buddy.db.models import JSONFile


def decrypt_string(encrypted: str) -> str:
    key = Fernet(CONFIG.fernet_key)
    return key.decrypt(encrypted.encode()).decode()


def encrypt_string(string: str) -> str:
    key = Fernet(CONFIG.fernet_key)
    return key.encrypt(string.encode()).decode()


async def fetch_json_file(filename: str) -> Any:
    return await JSONFile.read(filename)
