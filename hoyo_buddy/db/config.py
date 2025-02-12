from __future__ import annotations

from hoyo_buddy.bot.config import CONFIG

DB_CONFIG = {
    "connections": {"default": CONFIG.db_url},
    "apps": {
        "models": {
            "models": ["hoyo_buddy.db.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "minsize": 1,
    "maxsize": 20,
}
